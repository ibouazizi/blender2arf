#!/usr/bin/env python3
"""
Consolidated GLB exporter with external texture support.
Always exports textures as external files for reuse.
"""

import bpy
import struct
import json
import numpy as np
import os
from io import BytesIO
from typing import Dict, List, Any, Optional, Tuple

# Import utilities
from uv_utils import convert_blender_uv_to_gltf
from external_texture_manager import ExternalTextureManager


def convert_blender_to_gltf_matrix(matrix):
    """Convert Blender's coordinate system to glTF."""
    # Blender: Z-up, Y-forward, X-right
    # glTF: Y-up, Z-forward, X-right
    conversion = np.array([
        [1, 0, 0, 0],
        [0, 0, 1, 0],
        [0, -1, 0, 0],
        [0, 0, 0, 1]
    ])
    return conversion @ matrix @ conversion.T


def convert_blender_to_gltf_coords(coords):
    """Convert Blender coordinates to glTF coordinates."""
    return [coords[0], coords[2], -coords[1]]


def convert_blender_to_gltf_normal(normal):
    """Convert Blender normal to glTF normal."""
    return [normal[0], normal[2], -normal[1]]


def convert_blender_to_gltf_quaternion(q):
    """Convert Blender quaternion to glTF quaternion."""
    # Blender: W, X, Y, Z
    # glTF: X, Y, Z, W
    # Also need coordinate system conversion
    return [q[1], q[3], -q[2], q[0]]


def extract_texture_from_node(node, socket_name):
    """Extract texture from a shader node socket."""
    if socket_name in node.inputs:
        socket = node.inputs[socket_name]
        if socket.is_linked:
            for link in socket.links:
                from_node = link.from_node
                if from_node.type == 'TEX_IMAGE' and from_node.image:
                    return from_node.image
    return None


def encode_image_to_buffer(image):
    """Encode a Blender image to bytes."""
    if not image:
        return None, None
        
    # Handle packed files
    if image.packed_file:
        return image.packed_file.data, 'image/png'
    
    # Handle external files
    filepath = bpy.path.abspath(image.filepath)
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            image_data = f.read()
        
        # Determine MIME type
        ext = os.path.splitext(filepath)[1].lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }.get(ext, 'image/png')
        
        return image_data, mime_type
    
    return None, None


class SimpleGLBGenerator:
    """Simplified GLB generator with external texture support."""
    
    def __init__(self, texture_manager: ExternalTextureManager):
        self.buffer_data = BytesIO()
        self.accessors = []
        self.buffer_views = []
        self.materials = []
        self.textures = []
        self.images = []
        self.samplers = []
        self.texture_manager = texture_manager
        
    def add_accessor(self, buffer_view_idx, byte_offset, component_type, count, accessor_type, min_vals=None, max_vals=None):
        """Add an accessor to the glTF."""
        accessor = {
            "bufferView": buffer_view_idx,
            "byteOffset": byte_offset,
            "componentType": component_type,
            "count": count,
            "type": accessor_type
        }
        
        if min_vals is not None:
            accessor["min"] = min_vals
        if max_vals is not None:
            accessor["max"] = max_vals
            
        self.accessors.append(accessor)
        return len(self.accessors) - 1
        
    def add_buffer_view(self, byte_offset, byte_length, target=None):
        """Add a buffer view to the glTF."""
        view = {
            "buffer": 0,
            "byteOffset": byte_offset,
            "byteLength": byte_length
        }
        if target is not None:
            view["target"] = target
            
        self.buffer_views.append(view)
        return len(self.buffer_views) - 1
        
    def add_primitive_data(self, data, component_type, accessor_type, target=None):
        """Add primitive data (vertices, normals, etc.) to the buffer."""
        # Ensure proper alignment
        padding = (4 - (self.buffer_data.tell() % 4)) % 4
        if padding:
            self.buffer_data.write(b'\x00' * padding)
            
        byte_offset = self.buffer_data.tell()
        data_bytes = data.tobytes()
        self.buffer_data.write(data_bytes)
        
        # Create buffer view
        buffer_view_idx = self.add_buffer_view(byte_offset, len(data_bytes), target)
        
        # Calculate min/max for position data
        min_vals = None
        max_vals = None
        if accessor_type == "VEC3" and data.shape[1] == 3:
            min_vals = data.min(axis=0).tolist()
            max_vals = data.max(axis=0).tolist()
            
        # Create accessor
        accessor_idx = self.add_accessor(
            buffer_view_idx, 0, component_type,
            len(data), accessor_type, min_vals, max_vals
        )
        
        return accessor_idx
        
    def add_external_texture(self, image_data: bytes, image_name: str, mime_type: str, asset_name: str = None) -> int:
        """Add texture as external file and return texture index."""
        # Get external texture URI
        filename, relative_uri = self.texture_manager.register_texture(image_data, image_name, mime_type, asset_name)
        
        # Create texture entry
        texture_idx = len(self.textures)
        self.textures.append({
            'source': len(self.images),
            'sampler': 0
        })
        
        # Create image entry with URI
        self.images.append({
            'name': image_name,
            'uri': relative_uri,
            'mimeType': mime_type
        })
        
        # Ensure default sampler exists
        if not self.samplers:
            self.samplers.append({
                'magFilter': 9729,  # LINEAR
                'minFilter': 9987,  # LINEAR_MIPMAP_LINEAR
                'wrapS': 10497,     # REPEAT
                'wrapT': 10497      # REPEAT
            })
        
        return texture_idx
        
    def create_glb(self, mesh_data: Dict[str, Any], materials_data: List[Dict[str, Any]]) -> bytes:
        """Create a GLB file from mesh data."""
        self.materials = materials_data or []
        
        # Build glTF structure
        gltf = {
            "asset": {
                "version": "2.0",
                "generator": "Blender ARF Exporter"
            },
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": []
        }
        
        # Add materials and textures
        if self.materials:
            gltf["materials"] = self.materials
        if self.textures:
            gltf["textures"] = self.textures
        if self.images:
            gltf["images"] = self.images
        if self.samplers:
            gltf["samplers"] = self.samplers
        
        # Process mesh
        mesh_json = {
            "name": mesh_data.get('name', 'mesh'),
            "primitives": []
        }
        
        for primitive in mesh_data.get('primitives', []):
            prim_json = self._process_primitive(primitive)
            if prim_json:
                mesh_json["primitives"].append(prim_json)
        
        gltf["meshes"].append(mesh_json)
        
        # Add accessors and buffer views
        gltf["accessors"] = self.accessors
        gltf["bufferViews"] = self.buffer_views
        
        # Add buffer
        buffer_length = self.buffer_data.tell()
        gltf["buffers"] = [{"byteLength": buffer_length}]
        
        # Create GLB
        return self._create_glb_binary(gltf, self.buffer_data.getvalue())
        
    def _process_primitive(self, primitive: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single primitive."""
        prim_json = {
            "attributes": {},
            "mode": 4  # TRIANGLES
        }
        
        # Process attributes
        for attr_name, data in primitive.get('attributes', {}).items():
            if isinstance(data, np.ndarray):
                component_type = 5126  # FLOAT
                if attr_name == "POSITION":
                    accessor_idx = self.add_primitive_data(data, component_type, "VEC3", 34962)
                elif attr_name == "NORMAL":
                    accessor_idx = self.add_primitive_data(data, component_type, "VEC3", 34962)
                elif attr_name == "TEXCOORD_0":
                    accessor_idx = self.add_primitive_data(data, component_type, "VEC2", 34962)
                else:
                    continue
                prim_json["attributes"][attr_name] = accessor_idx
        
        # Process indices
        indices = primitive.get('indices')
        if isinstance(indices, np.ndarray):
            accessor_idx = self.add_primitive_data(indices, 5125, "SCALAR", 34963)  # UNSIGNED_INT
            prim_json["indices"] = accessor_idx
        
        # Add material
        if 'material' in primitive:
            prim_json["material"] = primitive['material']
        
        return prim_json
        
    def _create_glb_binary(self, gltf: Dict[str, Any], buffer_data: bytes) -> bytes:
        """Create the final GLB binary."""
        # Convert glTF to JSON
        json_str = json.dumps(gltf, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        
        # Pad JSON to 4-byte boundary
        json_padding = (4 - (len(json_bytes) % 4)) % 4
        json_bytes += b' ' * json_padding
        
        # Pad buffer to 4-byte boundary
        buffer_padding = (4 - (len(buffer_data) % 4)) % 4
        buffer_data += b'\x00' * buffer_padding
        
        # Calculate total length
        total_length = 12 + 8 + len(json_bytes) + 8 + len(buffer_data)
        
        # Create GLB
        glb = BytesIO()
        
        # Header
        glb.write(b'glTF')
        glb.write(struct.pack('<I', 2))  # Version
        glb.write(struct.pack('<I', total_length))
        
        # JSON chunk
        glb.write(struct.pack('<I', len(json_bytes)))
        glb.write(struct.pack('<I', 0x4E4F534A))  # JSON
        glb.write(json_bytes)
        
        # Binary chunk
        glb.write(struct.pack('<I', len(buffer_data)))
        glb.write(struct.pack('<I', 0x004E4942))  # BIN
        glb.write(buffer_data)
        
        return glb.getvalue()


def export_mesh_to_glb(mesh_obj, output_path: str, texture_manager: ExternalTextureManager, 
                      scale: float = 1.0, asset_name: str = None, include_materials: bool = True) -> bool:
    """
    Export a mesh to GLB with external textures.
    
    Args:
        mesh_obj: Blender mesh object
        output_path: Path for output GLB file
        texture_manager: Manager for external texture files
        scale: Scale factor for export
        asset_name: Name of the asset this mesh belongs to
        include_materials: Whether to include materials and textures (False for blendshapes)
        
    Returns:
        bool: Success status
    """
    try:
        # Removed verbose logging for export path
        
        # Get evaluated mesh
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        eval_mesh.calc_loop_triangles()
        
        # Group triangles by material
        material_primitives = {}
        
        for tri in eval_mesh.loop_triangles:
            mat_idx = tri.material_index
            if mat_idx not in material_primitives:
                material_primitives[mat_idx] = {
                    'vertices': [],
                    'normals': [],
                    'uvs': [],
                    'indices': [],
                    'vertex_map': {}
                }
            
            prim_data = material_primitives[mat_idx]
            
            for i in range(3):
                loop_idx = tri.loops[i]
                vert_idx = eval_mesh.loops[loop_idx].vertex_index
                vert = eval_mesh.vertices[vert_idx]
                
                # Get UV coordinates
                uv = [0.0, 0.0]
                if eval_mesh.uv_layers.active:
                    raw_uv = eval_mesh.uv_layers.active.data[loop_idx].uv
                    # Convert from Blender UV to glTF UV coordinate system
                    u, v = convert_blender_uv_to_gltf(raw_uv[0], raw_uv[1])
                    uv = [u, v]
                
                # Create unique vertex key
                vert_key = (vert_idx, tuple(uv))
                
                if vert_key not in prim_data['vertex_map']:
                    new_idx = len(prim_data['vertices'])
                    prim_data['vertex_map'][vert_key] = new_idx
                    
                    # Apply scale and coordinate conversion
                    scaled_pos = [coord * scale for coord in vert.co]
                    converted_pos = convert_blender_to_gltf_coords(scaled_pos)
                    converted_normal = convert_blender_to_gltf_normal(list(vert.normal))
                    
                    prim_data['vertices'].append(converted_pos)
                    prim_data['normals'].append(converted_normal)
                    prim_data['uvs'].append(uv)
                
                prim_data['indices'].append(prim_data['vertex_map'][vert_key])
        
        # Create GLB generator
        generator = SimpleGLBGenerator(texture_manager)
        
        # Process materials only if requested
        materials_data = []
        if include_materials:
            for idx, mat_slot in enumerate(mesh_obj.material_slots):
                mat_data = {
                    'name': mat_slot.material.name if mat_slot.material else f"Material_{idx}",
                    'pbrMetallicRoughness': {
                        'baseColorFactor': [1.0, 1.0, 1.0, 1.0],
                        'metallicFactor': 0.0,
                        'roughnessFactor': 1.0
                    },
                    'alphaMode': 'OPAQUE',
                    'doubleSided': True
                }
                
                if mat_slot.material and mat_slot.material.use_nodes:
                    # Find principled BSDF node
                    for node in mat_slot.material.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            # Base color
                            base_color = node.inputs['Base Color'].default_value
                            mat_data['pbrMetallicRoughness']['baseColorFactor'] = [
                                base_color[0], base_color[1], base_color[2], base_color[3]
                            ]
                            
                            # Base color texture
                            base_color_image = extract_texture_from_node(node, 'Base Color')
                            if base_color_image:
                                image_data, mime_type = encode_image_to_buffer(base_color_image)
                                if image_data:
                                    tex_idx = generator.add_external_texture(
                                        image_data, base_color_image.name, mime_type, asset_name
                                    )
                                    mat_data['pbrMetallicRoughness']['baseColorTexture'] = {
                                        'index': tex_idx,
                                        'texCoord': 0
                                    }
                            
                            # Metallic/Roughness
                            mat_data['pbrMetallicRoughness']['metallicFactor'] = node.inputs['Metallic'].default_value
                            mat_data['pbrMetallicRoughness']['roughnessFactor'] = node.inputs['Roughness'].default_value
                            break
                
                materials_data.append(mat_data)
        
        # Create final primitives
        final_primitives = []
        for mat_idx, prim_data in sorted(material_primitives.items()):
            if not prim_data['vertices']:
                continue
                
            primitive = {
                'attributes': {
                    'POSITION': np.array(prim_data['vertices'], dtype=np.float32),
                    'NORMAL': np.array(prim_data['normals'], dtype=np.float32),
                    'TEXCOORD_0': np.array(prim_data['uvs'], dtype=np.float32)
                },
                'indices': np.array(prim_data['indices'], dtype=np.uint32)
            }
            # Only add material reference if including materials
            if include_materials:
                primitive['material'] = mat_idx
            final_primitives.append(primitive)
        
        # Create mesh data
        mesh_data = {
            'name': mesh_obj.name,
            'primitives': final_primitives
        }
        
        # Generate GLB
        glb_data = generator.create_glb(mesh_data, materials_data)
        
        # Write GLB file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        # Export completed successfully
        
        return True
        
    except Exception as e:
        print(f"Error exporting mesh {mesh_obj.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_blendshape_to_glb_simple(mesh_obj, shape_key_name: str, output_path: str, scale: float = 1.0) -> bool:
    """
    Export a single shape key as a GLB file containing delta positions.
    
    Args:
        mesh_obj: Blender mesh object with shape keys
        shape_key_name: Name of the shape key to export
        output_path: Path for output GLB file
        scale: Scale factor for export
        
    Returns:
        bool: Success status
    """
    try:
        # Exporting blendshape (verbose logging removed)
        
        # Verify shape key exists
        if not mesh_obj.data.shape_keys:
            print(f"No shape keys found on {mesh_obj.name}")
            return False
            
        shape_keys = mesh_obj.data.shape_keys.key_blocks
        if shape_key_name not in shape_keys:
            print(f"Shape key '{shape_key_name}' not found on {mesh_obj.name}")
            return False
            
        # Get basis and target shape keys
        basis = shape_keys.get("Basis") or shape_keys[0]
        target = shape_keys[shape_key_name]
        
        # Get evaluated mesh
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        eval_mesh.calc_loop_triangles()
        
        # Collect vertex positions from basis and target
        basis_positions = []
        target_positions = []
        
        for i, vert in enumerate(eval_mesh.vertices):
            # Get basis position
            basis_pos = basis.data[i].co
            target_pos = target.data[i].co
            
            # Apply scale and coordinate conversion
            basis_scaled = [coord * scale for coord in basis_pos]
            target_scaled = [coord * scale for coord in target_pos]
            
            basis_converted = convert_blender_to_gltf_coords(basis_scaled)
            target_converted = convert_blender_to_gltf_coords(target_scaled)
            
            basis_positions.append(basis_converted)
            target_positions.append(target_converted)
        
        # Calculate deltas
        deltas = []
        for basis_pos, target_pos in zip(basis_positions, target_positions):
            delta = [target_pos[i] - basis_pos[i] for i in range(3)]
            deltas.append(delta)
        
        # Create a simple GLB with just the delta positions
        generator = SimpleGLBGenerator(None)  # No texture manager needed for blendshapes
        
        # Add delta positions as the only attribute
        positions_array = np.array(deltas, dtype=np.float32)
        
        # Create mesh data with single primitive
        mesh_data = {
            'name': f"{mesh_obj.name}_{shape_key_name}",
            'primitives': [{
                'attributes': {
                    'POSITION': positions_array
                },
                'mode': 0  # POINTS mode since we only have positions
            }]
        }
        
        # Generate GLB without materials
        glb_data = generator.create_glb(mesh_data, [])
        
        # Write GLB file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        # Blendshape export completed
        return True
        
    except Exception as e:
        print(f"Error exporting blendshape {shape_key_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_mesh_with_shape_key_applied(mesh_obj, shape_values: Dict[str, float], output_path: str, 
                                      scale: float = 1.0, include_materials: bool = True) -> bool:
    """
    Export a mesh with specific shape key values applied.
    
    Args:
        mesh_obj: Blender mesh object with shape keys
        shape_values: Dictionary mapping shape key names to their values (0.0 to 1.0)
        output_path: Path for output GLB file
        scale: Scale factor for export
        include_materials: Whether to include materials in the export
        
    Returns:
        bool: Success status
    """
    try:
        # Exporting mesh with shape keys applied (verbose logging removed)
        
        # Store original shape key values
        original_values = {}
        if mesh_obj.data.shape_keys:
            for key in mesh_obj.data.shape_keys.key_blocks:
                original_values[key.name] = key.value
                # Apply requested values
                if key.name in shape_values:
                    key.value = shape_values[key.name]
        
        try:
            # Create a temporary texture manager if materials are included
            texture_manager = ExternalTextureManager(os.path.dirname(output_path)) if include_materials else None
            
            # Export the mesh with shape keys applied
            success = export_mesh_to_glb(mesh_obj, output_path, texture_manager, scale, include_materials=include_materials)
            
            return success
            
        finally:
            # Restore original shape key values
            if mesh_obj.data.shape_keys:
                for key_name, value in original_values.items():
                    if key_name in mesh_obj.data.shape_keys.key_blocks:
                        mesh_obj.data.shape_keys.key_blocks[key_name].value = value
        
    except Exception as e:
        print(f"Error exporting mesh with shape keys: {e}")
        import traceback
        traceback.print_exc()
        return False

