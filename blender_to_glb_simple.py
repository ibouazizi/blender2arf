#!/usr/bin/env python3
"""
Simplified Blender mesh to GLB converter without external dependencies.
Uses only Blender's built-in modules.
"""

import bpy
import struct
import json
import numpy as np
from io import BytesIO
from typing import Dict, List, Any, Optional

def convert_blender_to_gltf_coords(pos):
    """Convert from Blender's Z-up to glTF's Y-up coordinate system.
    Blender: X-right, Y-forward, Z-up
    glTF: X-right, Y-up, Z-forward
    """
    if len(pos) == 3:
        # Swap Y and Z coordinates
        return [pos[0], pos[2], -pos[1]]
    return pos

def convert_blender_to_gltf_normal(normal):
    """Convert normal vectors from Blender to glTF coordinate system."""
    if len(normal) == 3:
        # Swap Y and Z components  
        return [normal[0], normal[2], -normal[1]]
    return normal

def convert_blender_to_gltf_quaternion(quat):
    """Convert quaternion from Blender to glTF coordinate system.
    Blender uses WXYZ, glTF uses XYZW order."""
    if len(quat) == 4:
        # First reorder from WXYZ to XYZW if needed
        # Then apply axis swap for coordinate system
        # The quaternion needs to be adjusted for the axis swap
        x, y, z, w = quat[1], quat[2], quat[3], quat[0]
        # Swap Y and Z, negate the appropriate component
        return [x, z, -y, w]
    return quat

def convert_blender_to_gltf_matrix(matrix):
    """Convert a 4x4 matrix from Blender to glTF coordinate system."""
    # Create conversion matrix (swap Y and Z axes)
    conversion = np.array([
        [1, 0, 0, 0],
        [0, 0, 1, 0],
        [0, -1, 0, 0],
        [0, 0, 0, 1]
    ])
    
    # Convert matrix to numpy array if needed
    if hasattr(matrix, 'to_4x4'):
        mat = np.array(matrix.to_4x4())
    else:
        mat = np.array(matrix).reshape(4, 4)
    
    # Apply conversion: glTF_matrix = conversion @ blender_matrix @ conversion.T
    result = conversion @ mat @ conversion.T
    return result.flatten().tolist()


class SimpleGLBGenerator:
    """Simplified GLB generator using only built-in modules."""
    
    # glTF constants
    GLTF_MAGIC = 0x46546C67  # ASCII string 'glTF'
    GLTF_VERSION = 2
    JSON_CHUNK_TYPE = 0x4E4F534A  # ASCII string 'JSON'
    BIN_CHUNK_TYPE = 0x004E4942   # ASCII string 'BIN\0'
    
    # Component types
    COMPONENT_TYPES = {
        'int8': 5120,
        'uint8': 5121,
        'int16': 5122,
        'uint16': 5123,
        'uint32': 5125,
        'float32': 5126,
    }
    
    # Type strings
    TYPE_STRINGS = {
        1: "SCALAR",
        2: "VEC2",
        3: "VEC3",
        4: "VEC4",
        9: "MAT3",
        16: "MAT4"
    }
    
    def __init__(self):
        self.buffer_data = BytesIO()
        self.accessors = []
        self.buffer_views = []
        self.materials = []
        
    def create_glb(self, mesh_data: Dict[str, Any], materials_data: Optional[List[Dict[str, Any]]] = None) -> bytes:
        """Create a GLB file from mesh data."""
        # Reset state
        self.buffer_data = BytesIO()
        self.accessors = []
        self.buffer_views = []
        self.materials = materials_data or []
        
        # Build glTF structure
        gltf = {
            "asset": {
                "version": "2.0",
                "generator": "Blender ARF Exporter Simple GLB"
            },
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": []
        }
        
        # Process materials if provided
        if self.materials:
            gltf["materials"] = self.materials
        
        # Process mesh
        mesh_json = self._process_mesh(mesh_data)
        
        # Only add mesh if it has valid primitives
        if mesh_json["primitives"]:
            gltf["meshes"].append(mesh_json)
        else:
            # Create a minimal valid mesh with a single triangle
            self._create_minimal_mesh(gltf)
        
        # Add accessors and buffer views
        if self.accessors:
            gltf["accessors"] = self.accessors
        if self.buffer_views:
            gltf["bufferViews"] = self.buffer_views
        
        # Add buffer
        buffer_length = self.buffer_data.tell()
        if buffer_length > 0:
            gltf["buffers"] = [{"byteLength": buffer_length}]
        else:
            # Add a minimal buffer
            self.buffer_data.write(b'\x00' * 4)
            gltf["buffers"] = [{"byteLength": 4}]
        
        # Create GLB
        return self._create_glb_binary(gltf, self.buffer_data.getvalue())
    
    def _process_mesh(self, mesh_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process mesh data and create glTF mesh object."""
        mesh_json = {
            "name": mesh_data.get('name', 'mesh'),
            "primitives": []
        }
        
        for primitive in mesh_data.get('primitives', []):
            prim_json = self._process_primitive(primitive)
            if prim_json is not None:
                mesh_json["primitives"].append(prim_json)
        
        return mesh_json
    
    def _process_primitive(self, primitive: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single primitive."""
        prim_json = {
            "attributes": {},
            "mode": primitive.get('mode', 4)  # Default to TRIANGLES
        }
        
        # Process attributes
        has_attributes = False
        for attr_name, data in primitive.get('attributes', {}).items():
            if isinstance(data, np.ndarray):
                accessor_idx = self._add_accessor(data, attr_name)
                prim_json["attributes"][attr_name] = accessor_idx
                has_attributes = True
        
        # Skip primitive if it has no attributes
        if not has_attributes:
            return None
        
        # Process indices
        indices = primitive.get('indices')
        if indices is not None and isinstance(indices, np.ndarray):
            accessor_idx = self._add_accessor(indices, 'INDICES')
            prim_json["indices"] = accessor_idx
        
        # Add material if present
        if 'material' in primitive and primitive['material'] is not None:
            prim_json["material"] = primitive['material'] % len(self.materials) if self.materials else 0
        
        return prim_json
    
    def _add_accessor(self, data: np.ndarray, attribute_type: str) -> int:
        """Add accessor for numpy array data."""
        # Ensure data is C-contiguous
        if not data.flags['C_CONTIGUOUS']:
            data = np.ascontiguousarray(data)
        
        # Determine component type
        dtype_map = {
            np.dtype(np.int8): 5120,
            np.dtype(np.uint8): 5121,
            np.dtype(np.int16): 5122,
            np.dtype(np.uint16): 5123,
            np.dtype(np.uint32): 5125,
            np.dtype(np.float32): 5126,
        }
        component_type = dtype_map.get(data.dtype, 5126)  # Default to FLOAT
        
        # Determine type string
        if data.ndim == 1:
            count = data.shape[0]
            type_str = "SCALAR"
        else:
            count = data.shape[0]
            num_components = data.shape[1]
            type_str = self.TYPE_STRINGS.get(num_components, "SCALAR")
        
        # Calculate min/max for certain attributes
        accessor = {
            "bufferView": len(self.buffer_views),
            "componentType": component_type,
            "count": count,
            "type": type_str
        }
        
        # Add min/max for position
        if attribute_type == "POSITION" and data.ndim == 2 and data.shape[1] == 3:
            accessor["min"] = data.min(axis=0).tolist()
            accessor["max"] = data.max(axis=0).tolist()
        
        # Create buffer view
        byte_offset = self.buffer_data.tell()
        byte_length = data.nbytes
        
        buffer_view = {
            "buffer": 0,
            "byteOffset": byte_offset,
            "byteLength": byte_length
        }
        
        # Add target for vertex attributes
        if attribute_type in ["POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "TEXCOORD_1", "COLOR_0", "JOINTS_0", "WEIGHTS_0"]:
            buffer_view["target"] = 34962  # ARRAY_BUFFER
        elif attribute_type == "INDICES":
            buffer_view["target"] = 34963  # ELEMENT_ARRAY_BUFFER
        
        # Write data to buffer
        self.buffer_data.write(data.tobytes())
        
        # Align to 4-byte boundary
        padding = (4 - (self.buffer_data.tell() % 4)) % 4
        if padding:
            self.buffer_data.write(b'\x00' * padding)
        
        # Add to lists
        self.buffer_views.append(buffer_view)
        self.accessors.append(accessor)
        
        return len(self.accessors) - 1
    
    def _create_minimal_mesh(self, gltf: Dict[str, Any]):
        """Create a minimal valid mesh with a single triangle."""
        # Create a simple triangle
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0]
        ], dtype=np.float32)
        
        # Add position accessor
        pos_accessor_idx = self._add_accessor(positions, 'POSITION')
        
        # Create primitive
        primitive = {
            "attributes": {
                "POSITION": pos_accessor_idx
            },
            "mode": 4  # TRIANGLES
        }
        
        # Create mesh
        mesh = {
            "name": "minimal_mesh",
            "primitives": [primitive]
        }
        
        gltf["meshes"].append(mesh)
    
    def _create_glb_binary(self, gltf: Dict[str, Any], buffer_data: bytes) -> bytes:
        """Create binary GLB from glTF JSON and buffer data."""
        # Convert JSON to bytes
        json_str = json.dumps(gltf, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        
        # Pad JSON to 4-byte boundary
        json_padding = (4 - (len(json_bytes) % 4)) % 4
        json_bytes += b' ' * json_padding
        
        # Calculate total length
        header_length = 12
        json_chunk_length = 8 + len(json_bytes)
        bin_chunk_length = 8 + len(buffer_data) if buffer_data else 0
        total_length = header_length + json_chunk_length + bin_chunk_length
        
        # Create GLB
        glb = BytesIO()
        
        # Write header
        glb.write(struct.pack('<III', self.GLTF_MAGIC, self.GLTF_VERSION, total_length))
        
        # Write JSON chunk
        glb.write(struct.pack('<II', len(json_bytes), self.JSON_CHUNK_TYPE))
        glb.write(json_bytes)
        
        # Write binary chunk if present
        if buffer_data:
            # Pad buffer to 4-byte boundary
            buffer_padding = (4 - (len(buffer_data) % 4)) % 4
            padded_buffer = buffer_data + b'\x00' * buffer_padding
            
            glb.write(struct.pack('<II', len(padded_buffer), self.BIN_CHUNK_TYPE))
            glb.write(padded_buffer)
        
        return glb.getvalue()


def export_mesh_to_glb_simple(mesh_obj: bpy.types.Object, output_path: str, 
                              include_skin: bool = False, 
                              armature_obj: Optional[bpy.types.Object] = None,
                              scale: float = 1.0) -> bool:
    """Export a single mesh object to GLB file using simple GLB generator."""
    try:
        mesh = mesh_obj.data
        
        # Ensure mesh is in a good state for export
        mesh.calc_loop_triangles()
        # Note: calc_normals_split was removed in newer Blender versions
        # mesh.calc_normals_split()
        
        # Get the evaluated mesh (with modifiers applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        
        # Extract vertices, normals, and UVs
        vertices = []
        normals = []
        uvs = []
        
        # Get vertices with scale applied and coordinate conversion
        for vert in eval_mesh.vertices:
            # Apply scale to vertex positions
            scaled_pos = [coord * scale for coord in vert.co]
            # Convert from Blender Z-up to glTF Y-up
            converted_pos = convert_blender_to_gltf_coords(scaled_pos)
            vertices.append(converted_pos)
            # Convert normal vector
            converted_normal = convert_blender_to_gltf_normal(list(vert.normal))
            normals.append(converted_normal)
        
        # Get UVs if available
        if eval_mesh.uv_layers.active:
            uv_layer = eval_mesh.uv_layers.active.data
            for poly in eval_mesh.polygons:
                for loop_idx in poly.loop_indices:
                    uvs.append(list(uv_layer[loop_idx].uv))
        
        # Get faces (as triangles)
        indices = []
        for tri in eval_mesh.loop_triangles:
            indices.extend(tri.vertices)
        
        # Convert to numpy arrays
        attributes = {
            'POSITION': np.array(vertices, dtype=np.float32),
            'NORMAL': np.array(normals, dtype=np.float32)
        }
        
        if uvs:
            # For now, just use first UV (simplified)
            attributes['TEXCOORD_0'] = np.array(uvs[:len(vertices)], dtype=np.float32)
        
        # Add skinning data if requested
        if include_skin and armature_obj and mesh_obj.vertex_groups:
            # Simplified skinning - just add empty data for now
            num_verts = len(vertices)
            attributes['JOINTS_0'] = np.zeros((num_verts, 4), dtype=np.uint8)
            attributes['WEIGHTS_0'] = np.array([[1.0, 0.0, 0.0, 0.0]] * num_verts, dtype=np.float32)
        
        # Create mesh data
        mesh_data = {
            'name': mesh_obj.name,
            'primitives': [{
                'attributes': attributes,
                'indices': np.array(indices, dtype=np.uint32),
                'material': 0
            }]
        }
        
        # Extract material data from mesh
        materials_data = []
        material_indices = {}
        
        # Collect materials from mesh
        for idx, mat_slot in enumerate(mesh_obj.material_slots):
            if mat_slot.material:
                mat = mat_slot.material
                material_indices[mat.name] = idx
                
                # Extract PBR material properties
                mat_data = {
                    'name': mat.name,
                    'pbrMetallicRoughness': {},
                    'alphaMode': 'OPAQUE',
                    'doubleSided': True
                }
                
                # Get base color
                if mat.use_nodes:
                    # Try to find Principled BSDF node
                    for node in mat.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            # Base color
                            base_color = node.inputs['Base Color'].default_value
                            mat_data['pbrMetallicRoughness']['baseColorFactor'] = [
                                base_color[0], base_color[1], base_color[2], base_color[3]
                            ]
                            # Metallic and roughness
                            mat_data['pbrMetallicRoughness']['metallicFactor'] = node.inputs['Metallic'].default_value
                            mat_data['pbrMetallicRoughness']['roughnessFactor'] = node.inputs['Roughness'].default_value
                            # Alpha
                            if node.inputs['Alpha'].default_value < 1.0:
                                mat_data['alphaMode'] = 'BLEND'
                            break
                else:
                    # Fallback to viewport display color
                    mat_data['pbrMetallicRoughness']['baseColorFactor'] = [
                        mat.diffuse_color[0], mat.diffuse_color[1], 
                        mat.diffuse_color[2], mat.diffuse_color[3]
                    ]
                    mat_data['pbrMetallicRoughness']['metallicFactor'] = mat.metallic
                    mat_data['pbrMetallicRoughness']['roughnessFactor'] = mat.roughness
                
                materials_data.append(mat_data)
        
        # If no materials, add default
        if not materials_data:
            materials_data = [{
                'name': 'default',
                'pbrMetallicRoughness': {
                    'baseColorFactor': [0.8, 0.8, 0.8, 1.0],
                    'metallicFactor': 0.0,
                    'roughnessFactor': 1.0
                },
                'alphaMode': 'OPAQUE',
                'doubleSided': True
            }]
        
        # Create GLB
        generator = SimpleGLBGenerator()
        glb_data = generator.create_glb(mesh_data, materials_data)
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        return True
        
    except Exception as e:
        print(f"Error exporting {mesh_obj.name} to GLB: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# Also create simplified versions for skeleton and blendshape export
def export_skeleton_to_glb_simple(armature_obj: bpy.types.Object, output_path: str, scale: float = 1.0) -> bool:
    """Export skeleton as a simple point cloud GLB."""
    try:
        # Get bone positions with scale applied and coordinate conversion
        positions = []
        for bone in armature_obj.data.bones:
            scaled_pos = [coord * scale for coord in bone.head_local]
            # Convert from Blender Z-up to glTF Y-up
            converted_pos = convert_blender_to_gltf_coords(scaled_pos)
            positions.append(converted_pos)
        
        # Create mesh data
        mesh_data = {
            'name': f"{armature_obj.name}_skeleton",
            'primitives': [{
                'attributes': {
                    'POSITION': np.array(positions, dtype=np.float32)
                },
                'mode': 0  # POINTS
            }]
        }
        
        # Create GLB
        generator = SimpleGLBGenerator()
        glb_data = generator.create_glb(mesh_data)
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        return True
        
    except Exception as e:
        print(f"Error exporting skeleton {armature_obj.name}: {str(e)}")
        return False


def export_blendshape_to_glb_simple(mesh_obj: bpy.types.Object, shape_key_name: str, output_path: str) -> bool:
    """Export blendshape as delta positions."""
    try:
        mesh = mesh_obj.data
        if not mesh.shape_keys or shape_key_name not in mesh.shape_keys.key_blocks:
            return False
        
        # Get base and target shape
        basis = mesh.shape_keys.key_blocks[0]
        target = mesh.shape_keys.key_blocks[shape_key_name]
        
        # Calculate deltas with coordinate conversion
        positions = []
        for i, (basis_vert, target_vert) in enumerate(zip(basis.data, target.data)):
            delta = target_vert.co - basis_vert.co
            # Convert delta from Blender to glTF coordinates
            converted_delta = convert_blender_to_gltf_coords(list(delta))
            positions.append(converted_delta)
        
        # Create mesh data
        mesh_data = {
            'name': shape_key_name,
            'primitives': [{
                'attributes': {
                    'POSITION': np.array(positions, dtype=np.float32)
                },
                'mode': 0  # POINTS
            }]
        }
        
        # Create GLB
        generator = SimpleGLBGenerator()
        glb_data = generator.create_glb(mesh_data)
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        return True
        
    except Exception as e:
        print(f"Error exporting blendshape {shape_key_name}: {str(e)}")
        return False


def export_mesh_with_shape_key_applied(mesh_obj: bpy.types.Object, shape_key_values: dict, output_path: str, scale: float = 1.0) -> bool:
    """Export mesh with specific shape key values applied."""
    try:
        # Store original shape key values
        original_values = {}
        if mesh_obj.data.shape_keys:
            for key_block in mesh_obj.data.shape_keys.key_blocks:
                original_values[key_block.name] = key_block.value
                # Apply requested values
                if key_block.name in shape_key_values:
                    key_block.value = shape_key_values[key_block.name]
                else:
                    key_block.value = 0.0
        
        # Export the mesh with shape keys applied
        success = export_mesh_to_glb_simple(mesh_obj, output_path, include_skin=False, armature_obj=None, scale=scale)
        
        # Restore original values
        if mesh_obj.data.shape_keys:
            for key_block in mesh_obj.data.shape_keys.key_blocks:
                if key_block.name in original_values:
                    key_block.value = original_values[key_block.name]
        
        return success
        
    except Exception as e:
        print(f"Error exporting mesh with shape key: {str(e)}")
        return False