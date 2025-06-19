
# Command line to run Blender export: "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" "F:\workspace\ARF\Imed\Imed.blend" --background --python arf_export.py from F:\workspace 


bl_info = {
    "name": "ARF (Avatar Representation Format) Exporter",
    "author": "Imed Bouazizi",
    "version": (1, 1, 3),
    "blender": (2, 80, 0),
    "location": "File > Export > Avatar Representation Format (.zip)",
    "description": "Export avatar data in ARF format with tensor weights",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export"
}

import bpy
import json
import zipfile
import os
import uuid
import datetime
import math
import numpy as np
from mathutils import Matrix, Vector, Quaternion
from bpy_extras.io_utils import ExportHelper
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    EnumProperty,
    CollectionProperty
)

# Import ARF compliance utilities
try:
    from addons.arf_exporter.core.arf_compliance import (
        has_vertex_weights, 
        validate_metadata_compliance,
        fix_arf_compliance,
        remove_non_compliant_fields
    )
except ImportError:
    # Define fallback functions
    def has_vertex_weights(mesh_obj, armature_obj):
        """Check if mesh has vertex weights for armature"""
        if not mesh_obj or not armature_obj:
            return False
        bone_names = set(bone.name for bone in armature_obj.data.bones)
        mesh_vgroups = set(vg.name for vg in mesh_obj.vertex_groups)
        matching_groups = bone_names.intersection(mesh_vgroups)
        if not matching_groups:
            return False
        for vertex in mesh_obj.data.vertices:
            for group in vertex.groups:
                if group.weight > 0 and mesh_obj.vertex_groups[group.group].name in matching_groups:
                    return True
        return False
        
    def validate_metadata_compliance(metadata):
        return metadata
        
    def fix_arf_compliance(arf_data):
        return arf_data
        
    def remove_non_compliant_fields(arf_data):
        return arf_data

# Add script directory to path for imports
import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Import custom GLB exporter
from blender_to_glb_simple import (
    export_mesh_to_glb_simple, 
    export_skeleton_to_glb_simple,
    export_blendshape_to_glb_simple,
    export_mesh_with_shape_key_applied
)
# Debug point can be uncommented when needed
# import pdb; pdb.set_trace()

# Constants for the ARF format
ARF_SIGNATURE = "ARF"
ARF_VERSION = "1.0"

# Animation support constants
OPENXR_FACIAL_URN = "urn:khronos:openxr:facial-animation:fb-tracking2"
MPEG_BODY_URN = "urn:mpeg:avatar:animation:body:2024"
OPENXR_BODY_URN = "urn:khronos:openxr:body-tracking:fb-body"
MPEG_HAND_URN = "urn:mpeg:avatar:animation:hand:2024"

# OpenXR blendshape mapping
BLENDSHAPE_MAPPING = {
    # Map from common Blender shape key names to OpenXR standard names
    "brow_down_left": "XR_FACE_EXPRESSION2_BROW_LOWERER_L_FB",
    "brow_down_right": "XR_FACE_EXPRESSION2_BROW_LOWERER_R_FB",
    "cheek_puff_left": "XR_FACE_EXPRESSION2_CHEEK_PUFF_L_FB",
    "cheek_puff_right": "XR_FACE_EXPRESSION2_CHEEK_PUFF_R_FB",
    "cheek_raise_left": "XR_FACE_EXPRESSION2_CHEEK_RAISER_L_FB",
    "cheek_raise_right": "XR_FACE_EXPRESSION2_CHEEK_RAISER_R_FB",
    "eye_blink_left": "XR_FACE_EXPRESSION2_EYES_CLOSED_L_FB",
    "eye_blink_right": "XR_FACE_EXPRESSION2_EYES_CLOSED_R_FB",
    "eye_look_down_left": "XR_FACE_EXPRESSION2_EYES_LOOK_DOWN_L_FB",
    "eye_look_down_right": "XR_FACE_EXPRESSION2_EYES_LOOK_DOWN_R_FB",
    "eye_look_left_left": "XR_FACE_EXPRESSION2_EYES_LOOK_LEFT_L_FB",
    "eye_look_left_right": "XR_FACE_EXPRESSION2_EYES_LOOK_LEFT_R_FB",
    "eye_look_right_left": "XR_FACE_EXPRESSION2_EYES_LOOK_RIGHT_L_FB",
    "eye_look_right_right": "XR_FACE_EXPRESSION2_EYES_LOOK_RIGHT_R_FB",
    "eye_look_up_left": "XR_FACE_EXPRESSION2_EYES_LOOK_UP_L_FB",
    "eye_look_up_right": "XR_FACE_EXPRESSION2_EYES_LOOK_UP_R_FB",
    "jaw_open": "XR_FACE_EXPRESSION2_JAW_DROP_FB",
    "jaw_left": "XR_FACE_EXPRESSION2_JAW_SIDEWAYS_LEFT_FB",
    "jaw_right": "XR_FACE_EXPRESSION2_JAW_SIDEWAYS_RIGHT_FB",
    "jaw_forward": "XR_FACE_EXPRESSION2_JAW_THRUST_FB",
    "mouth_smile_left": "XR_FACE_EXPRESSION2_LIP_CORNER_PULLER_L_FB",
    "mouth_smile_right": "XR_FACE_EXPRESSION2_LIP_CORNER_PULLER_R_FB",
    "mouth_frown_left": "XR_FACE_EXPRESSION2_LIP_CORNER_DEPRESSOR_L_FB",
    "mouth_frown_right": "XR_FACE_EXPRESSION2_LIP_CORNER_DEPRESSOR_R_FB",
    "mouth_left": "XR_FACE_EXPRESSION2_MOUTH_LEFT_FB",
    "mouth_right": "XR_FACE_EXPRESSION2_MOUTH_RIGHT_FB",
    "mouth_pucker": "XR_FACE_EXPRESSION2_LIP_PUCKER_L_FB",
    "mouth_funnel": "XR_FACE_EXPRESSION2_LIP_FUNNELER_LB_FB",
    "nose_sneer_left": "XR_FACE_EXPRESSION2_NOSE_WRINKLER_L_FB",
    "nose_sneer_right": "XR_FACE_EXPRESSION2_NOSE_WRINKLER_R_FB",
    # Add more mappings as needed
}

# OpenXR Body Tracking skeleton mapping (XR_FB_body_tracking)
SKELETON_MAPPING = {
    # Map from common bone names to OpenXR Body Tracking standard
    "hips": "XR_BODY_JOINT_HIPS_FB",
    "spine": "XR_BODY_JOINT_SPINE_LOWER_FB",
    "spine1": "XR_BODY_JOINT_SPINE_MIDDLE_FB", 
    "spine2": "XR_BODY_JOINT_SPINE_UPPER_FB",
    "neck": "XR_BODY_JOINT_NECK_FB",
    "head": "XR_BODY_JOINT_HEAD_FB",
    
    # Left arm
    "shoulder.l": "XR_BODY_JOINT_LEFT_SHOULDER_FB",
    "upper_arm.l": "XR_BODY_JOINT_LEFT_SCAPULA_FB", 
    "forearm.l": "XR_BODY_JOINT_LEFT_ARM_LOWER_FB",
    "hand.l": "XR_BODY_JOINT_LEFT_HAND_WRIST_TWIST_FB",
    
    # Right arm  
    "shoulder.r": "XR_BODY_JOINT_RIGHT_SHOULDER_FB",
    "upper_arm.r": "XR_BODY_JOINT_RIGHT_SCAPULA_FB",
    "forearm.r": "XR_BODY_JOINT_RIGHT_ARM_LOWER_FB", 
    "hand.r": "XR_BODY_JOINT_RIGHT_HAND_WRIST_TWIST_FB",
    
    # Left leg
    "thigh.l": "XR_BODY_JOINT_LEFT_LEG_UPPER_FB",
    "shin.l": "XR_BODY_JOINT_LEFT_LEG_LOWER_FB",
    "foot.l": "XR_BODY_JOINT_LEFT_FOOT_ANKLE_TWIST_FB",
    
    # Right leg
    "thigh.r": "XR_BODY_JOINT_RIGHT_LEG_UPPER_FB", 
    "shin.r": "XR_BODY_JOINT_RIGHT_LEG_LOWER_FB",
    "foot.r": "XR_BODY_JOINT_RIGHT_FOOT_ANKLE_TWIST_FB",
}

# ============================================================================
# MINIMAL TENSOR CONVERTER - Embedded in V1
# ============================================================================

class MinimalTensorConverter:
    """Minimal tensor converter for skin weights - embedded in V1"""
    
    def __init__(self, precision='float32', max_influences=4):
        self.precision = precision
        self.max_influences = max_influences
        self.dtype_map = {
            'float32': (np.float32, 'f'),
            'float16': (np.float16, 'e'),
            'uint16': (np.uint16, 'H'),
            'uint8': (np.uint8, 'B')
        }
    
    def extract_and_export_weights(self, mesh_obj, armature_obj, output_dir, name):
        """Extract skin weights and export as ARF-compliant tensor files"""
        if not mesh_obj or not armature_obj:
            return None
            
        mesh = mesh_obj.data
        armature = armature_obj.data
        
        # Get bone names and create index mapping
        bone_names = [bone.name for bone in armature.bones]
        bone_indices = {name: idx for idx, name in enumerate(bone_names)}
        
        # Get vertex groups that correspond to bones
        valid_groups = {}
        for vg in mesh_obj.vertex_groups:
            if vg.name in bone_indices:
                valid_groups[vg.index] = bone_indices[vg.name]
        
        if not valid_groups:
            return None
        
        # Extract weights for each vertex
        num_vertices = len(mesh.vertices)
        
        # Arrays to store joint indices and weights
        joint_indices = np.zeros((num_vertices, self.max_influences), dtype=np.uint16)
        joint_weights = np.zeros((num_vertices, self.max_influences), dtype=np.float32)
        
        for vert_idx, vertex in enumerate(mesh.vertices):
            # Get all weights for this vertex
            influences = []
            
            for group in vertex.groups:
                if group.group in valid_groups and group.weight > 0.0:
                    bone_idx = valid_groups[group.group]
                    influences.append((bone_idx, group.weight))
            
            # Sort by weight (descending) and take top max_influences
            influences.sort(key=lambda x: x[1], reverse=True)
            influences = influences[:self.max_influences]
            
            # Normalize weights
            if influences:
                total_weight = sum(w for _, w in influences)
                if total_weight > 0:
                    influences = [(idx, w / total_weight) for idx, w in influences]
                
                # Fill arrays
                for i, (bone_idx, weight) in enumerate(influences):
                    joint_indices[vert_idx, i] = bone_idx
                    joint_weights[vert_idx, i] = weight
        
        # Create data directory for tensor files
        tensor_dir = os.path.join(output_dir, "data")
        os.makedirs(tensor_dir, exist_ok=True)
        
        # Export joint indices as ARF-compliant tensor
        indices_path = os.path.join(tensor_dir, f"{name}_joints.bin")
        self._export_arf_tensor(joint_indices, indices_path, 'uint16')
        
        # Export joint weights as ARF-compliant tensor
        weights_path = os.path.join(tensor_dir, f"{name}_weights.bin")
        dtype, _ = self.dtype_map[self.precision]
        
        if self.precision in ['uint16', 'uint8']:
            # Normalize to integer range
            max_val = 65535 if self.precision == 'uint16' else 255
            weights_data = (joint_weights * max_val).astype(dtype)
        else:
            weights_data = joint_weights.astype(dtype)
        
        self._export_arf_tensor(weights_data, weights_path, self.precision)
        
        # Return ARF-compliant data entries with proper IDs
        global _data_counter
        
        joints_data = {
            'id': _data_counter,
            'name': f"{name}_joints",
            'type': 'application/mpeg.arf.dense',
            'uri': f"data/{name}_joints.bin"
        }
        _data_counter += 1
        
        weights_data = {
            'id': _data_counter,
            'name': f"{name}_weights", 
            'type': 'application/mpeg.arf.dense',
            'uri': f"data/{name}_weights.bin"
        }
        _data_counter += 1
        
        return [joints_data, weights_data]
    
    def _export_arf_tensor(self, data, file_path, dtype_name):
        """Export tensor data in ARF-compliant format with proper headers"""
        import struct
        
        # ARF tensor format specification:
        # num_of_dims (int32) + dims (int32[num_of_dims]) + dtype (enum) + data
        
        # Map ARF dtype to glTF 2.0 component types (as per ARF spec)
        dtype_map = {
            'uint8': 5121,     # UNSIGNED_BYTE
            'uint16': 5123,    # UNSIGNED_SHORT  
            'float16': 5126,   # FLOAT (no specific float16 in glTF, use FLOAT)
            'float32': 5126    # FLOAT
        }
        
        shape = data.shape
        num_dims = len(shape)
        dtype_enum = dtype_map.get(dtype_name, 5126)  # Default to FLOAT
        
        with open(file_path, 'wb') as f:
            # Write num_of_dims (int32)
            f.write(struct.pack('<i', num_dims))
            
            # Write dims (int32[num_of_dims])
            for dim in shape:
                f.write(struct.pack('<i', dim))
            
            # Write dtype (enum as int32)
            f.write(struct.pack('<i', dtype_enum))
            
            # Write tensor data
            f.write(data.tobytes())
        
        print(f"Exported ARF tensor: {file_path}")
        print(f"  Shape: {shape}")
        print(f"  Dtype: {dtype_name} (glTF: {dtype_enum})")
        print(f"  Size: {os.path.getsize(file_path)} bytes")

class ARFExportSettings:
    def __init__(self):
        self.scale = 1.0
        self.export_animations = True
        self.export_blendshapes = True
        self.export_skeletons = True
        self.organize_by_collections = True
        self.export_textures = True
        self.export_lods = True
        self.optimize_mesh = False
        self.compress_textures = False
        self.include_preview = True
        self.apply_modifiers = True
        self.folder_structure = "organized"  # "organized" or "flat"
        self.debug_mode = True  # Added debug mode
        # Add tensor weight settings
        self.use_tensor_weights = True  # Default to tensor weights for better performance
        self.tensor_precision = 'float32'  # Options: float32, float16, uint16, uint8
        
        # XR Mapping settings
        self.create_face_mapping = True  # Create XR_FB_face_tracking2 mapping by default
        self.create_body_mapping = True  # Create XR_FB_body_tracking mapping by default
        self.blendshape_standard = 'OPENXR_FACE'  # Default to OpenXR Face standard
        self.skeleton_standard = 'OPENXR_BODY'  # Default to OpenXR Body standard


# Global counters for sequential component IDs
_mesh_counter = 0
_skin_counter = 0
_skeleton_counter = 0
_blendshape_counter = 0
_node_counter = 0
_data_counter = 0

def reset_component_counters():
    """Reset all component counters (useful for testing)."""
    global _mesh_counter, _skin_counter, _skeleton_counter
    global _blendshape_counter, _node_counter, _data_counter
    _mesh_counter = 0
    _skin_counter = 0
    _skeleton_counter = 0
    _blendshape_counter = 0
    _node_counter = 0
    _data_counter = 0


def matrix_to_list(matrix):
    """Convert Blender matrix to list format."""
    return [value for row in matrix for value in row]



def export_mesh_to_glb(obj, temp_dir, settings, armature=None, subfolder="meshes"):
    """Export a single mesh to GLB format using custom exporter."""
    global _data_counter
    
    print(f"\nExporting mesh: {obj.name}")
    
    # Get object name and transform before any operations
    obj_name = obj.name
    obj_transform = matrix_to_list(obj.matrix_world)
    
    # Create subfolder if it doesn't exist
    subfolder_path = os.path.join(temp_dir, subfolder)
    os.makedirs(subfolder_path, exist_ok=True)
    
    # Export path
    glb_path = os.path.join(subfolder_path, f"{obj_name}.glb")
    print(f"Exporting to: {glb_path}")
    
    try:
        # Determine export type
        if obj.type == 'MESH':
            include_skin = armature is not None
            success = export_mesh_to_glb_simple(obj, glb_path, include_skin=include_skin, armature_obj=armature)
        elif obj.type == 'ARMATURE':
            success = export_skeleton_to_glb_simple(obj, glb_path)
        else:
            print(f"ERROR: Unknown object type: {obj.type}")
            return None
            
        if success and os.path.exists(glb_path):
            size = os.path.getsize(glb_path)
            print(f"GLB export successful")
            print(f"GLB file size: {size/1024:.1f} KB")
            
            # Only return data if file was created successfully
            data_id = _data_counter
            _data_counter += 1
            return {
                "id": data_id,
                "name": obj_name,
                "type": "model/gltf-binary",
                "uri": f"{subfolder}/{obj_name}.glb",
                "transform": obj_transform
            }
        else:
            print(f"ERROR: Failed to export {obj_name}")
            return None
            
    except Exception as e:
        print(f"ERROR exporting {obj_name}: {str(e)}")
        if settings.debug_mode:
            import traceback
            traceback.print_exc()
        return None

def get_skeleton_data(obj):
    """Extract armature (skeleton) data in ARF format.
    In ARF, each joint is represented by a single position and transformation.
    """
    global _skeleton_counter, _node_counter
    
    if obj.type != 'ARMATURE':
        return None
        
    skeleton_id = _skeleton_counter
    _skeleton_counter += 1
    skeleton = {
        "name": obj.name,
        "id": skeleton_id,
        "root": None,  # Will set this to the root joint ID
        "joints": [],  # Will contain joint IDs
        "transform": matrix_to_list(obj.matrix_world)
    }
    
    # First pass: collect all bones and create nodes
    nodes = []
    id_map = {}  # Maps bone names to node IDs
    joint_ids = []
    
    for i, bone in enumerate(obj.data.bones):
        node_id = _node_counter
        _node_counter += 1
        id_map[bone.name] = node_id
        joint_ids.append(node_id)
        
        # Calculate bone transform
        if bone.parent:
            # Local transform relative to parent
            parent_matrix_inv = bone.parent.matrix_local.inverted()
            bone_matrix = parent_matrix_inv @ bone.matrix_local
        else:
            # Global transform for root bones
            bone_matrix = bone.matrix_local
        
        # Extract components
        loc, rot, scale = bone_matrix.decompose()
        
        # Create node entry
        node = {
            "name": bone.name,
            "id": node_id,
            "mapping": f"avatar/skeleton/{bone.name}",
            "transform": matrix_to_list(bone.matrix_local),
            "translation": [loc.x, loc.y, loc.z],
            "rotation": [rot.x, rot.y, rot.z, rot.w],
            "scale": [scale.x, scale.y, scale.z]
        }
        
        if bone.parent:
            node["parent"] = id_map[bone.parent.name]
            
        nodes.append(node)
        
        # Set root bone
        if not bone.parent and skeleton["root"] is None:
            skeleton["root"] = node_id
    
    # Second pass: add children
    for node in nodes:
        children = []
        for other_node in nodes:
            if "parent" in other_node and other_node["parent"] == node["id"]:
                children.append(other_node["id"])
                
        if children:
            node["children"] = children
    
    # Add joint IDs to skeleton
    skeleton["joints"] = joint_ids
    
    return skeleton, nodes

def extract_skin_data(mesh_obj, armature_obj, mesh_id, skeleton_id=None):
    """Extract skin data for a mesh bound to an armature."""
    if not mesh_obj or not armature_obj:
        return None
    
    # Generate unique ID for this skin (but don't include in the component)
    global _skin_counter
    skin_id = _skin_counter
    _skin_counter += 1
    
    # Use provided skeleton ID or default to 0
    if skeleton_id is None:
        skeleton_id = 0
    
    # Create the skin component according to ARF spec
    # Schema requires: name, mapping, skeleton, mesh, weights
    skin_data = {
        "name": f"{mesh_obj.name}_skin",
        "mapping": [],  # Empty mapping array as required
        "skeleton": skeleton_id,  # Reference to the skeleton
        "mesh": mesh_id,          # Reference to the mesh being skinned
        "weights": []  # Will be filled with tensor data references
    }
    
    # Store ID separately for internal use
    skin_data["_internal_id"] = skin_id
    
    return skin_data

def export_skin_weights(mesh_obj, armature_obj, temp_dir, settings):
    """Export skinning weights - now supports both GLB and tensor formats"""
    if not mesh_obj or not armature_obj:
        return None
    
    print(f"\nExporting skin weights for: {mesh_obj.name}")
    
    if settings.use_tensor_weights:
        # Use tensor format
        print(f"  Using tensor format (precision: {settings.tensor_precision})")
        
        converter = MinimalTensorConverter(
            precision=settings.tensor_precision,
            max_influences=4
        )
        
        skin_name = f"{mesh_obj.name}_skin"
        tensor_entries = converter.extract_and_export_weights(
            mesh_obj, armature_obj, temp_dir, skin_name
        )
        
        if tensor_entries:
            print(f"  Exported tensor weights: {len(tensor_entries)} files")
            for entry in tensor_entries:
                # Get file size for logging
                tensor_path = os.path.join(temp_dir, entry['uri'])
                if os.path.exists(tensor_path):
                    size_kb = os.path.getsize(tensor_path) / 1024
                    print(f"    {entry['name']}: {size_kb:.1f} KB")
            return tensor_entries
        else:
            print(f"  ERROR: Failed to export tensor weights")
            return None
    else:
        # Original GLB format
        print(f"  Using GLB format")
    
    # Create subfolder for skins if it doesn't exist
    skins_folder = os.path.join(temp_dir, "skins")
    os.makedirs(skins_folder, exist_ok=True)
    
    # Generate unique ID for this skin
    global _skin_counter
    skin_id = _skin_counter
    _skin_counter += 1
    skin_name = f"{mesh_obj.name}_skin"
    skin_path = os.path.join(skins_folder, f"{skin_name}.glb")
    
    try:
        # Export mesh with skinning data
        success = export_mesh_to_glb_simple(mesh_obj, skin_path, include_skin=True, armature_obj=armature_obj)
        
        if success and os.path.exists(skin_path):
            size_kb = os.path.getsize(skin_path) / 1024
            print(f"Exported skin weights: {skin_name} ({size_kb:.1f} KB)")
            
            # Create the data entry for the skin weights file
            skin_data_entry = {
                "id": skin_id,
                "name": skin_name,
                "type": "model/gltf-binary",
                "uri": f"skins/{skin_name}.glb"
            }
            return skin_data_entry
        else:
            print(f"ERROR: Failed to export skin weights for {mesh_obj.name}")
            return None
            
    except Exception as e:
        print(f"ERROR exporting skin weights: {str(e)}")
        if settings.debug_mode:
            import traceback
            traceback.print_exc()
        return None

def create_face_animation_link(blendshapes, settings):
    """Create ARF-compliant AnimationLink for face tracking mappings"""
    if not settings.create_face_mapping or not blendshapes:
        return None
        
    global _data_counter
    
    # Enhanced mapping for CC Base blendshapes to OpenXR Face Tracking v2
    cc_to_openxr_mapping = {
        # Eye blendshapes
        "eye_blink_l": "XR_FACE_EXPRESSION2_EYES_CLOSED_L_FB",
        "eye_blink_r": "XR_FACE_EXPRESSION2_EYES_CLOSED_R_FB",
        "eye_l_look_down": "XR_FACE_EXPRESSION2_EYES_LOOK_DOWN_L_FB",
        "eye_r_look_down": "XR_FACE_EXPRESSION2_EYES_LOOK_DOWN_R_FB",
        "eye_l_look_l": "XR_FACE_EXPRESSION2_EYES_LOOK_LEFT_L_FB",
        "eye_r_look_l": "XR_FACE_EXPRESSION2_EYES_LOOK_LEFT_R_FB",
        "eye_l_look_r": "XR_FACE_EXPRESSION2_EYES_LOOK_RIGHT_L_FB",
        "eye_r_look_r": "XR_FACE_EXPRESSION2_EYES_LOOK_RIGHT_R_FB",
        "eye_l_look_up": "XR_FACE_EXPRESSION2_EYES_LOOK_UP_L_FB",
        "eye_r_look_up": "XR_FACE_EXPRESSION2_EYES_LOOK_UP_R_FB",
        "eye_squint_l": "XR_FACE_EXPRESSION2_LID_TIGHTENER_L_FB",
        "eye_squint_r": "XR_FACE_EXPRESSION2_LID_TIGHTENER_R_FB",
        "eye_wide_l": "XR_FACE_EXPRESSION2_UPPER_LID_RAISER_L_FB",
        "eye_wide_r": "XR_FACE_EXPRESSION2_UPPER_LID_RAISER_R_FB",
        
        # Brow blendshapes
        "brow_raise_inner_l": "XR_FACE_EXPRESSION2_INNER_BROW_RAISER_L_FB",
        "brow_raise_inner_r": "XR_FACE_EXPRESSION2_INNER_BROW_RAISER_R_FB",
        "brow_raise_outer_l": "XR_FACE_EXPRESSION2_OUTER_BROW_RAISER_L_FB",
        "brow_raise_outer_r": "XR_FACE_EXPRESSION2_OUTER_BROW_RAISER_R_FB",
        "brow_drop_l": "XR_FACE_EXPRESSION2_BROW_LOWERER_L_FB",
        "brow_drop_r": "XR_FACE_EXPRESSION2_BROW_LOWERER_R_FB",
        
        # Cheek blendshapes
        "cheek_puff_l": "XR_FACE_EXPRESSION2_CHEEK_PUFF_L_FB",
        "cheek_puff_r": "XR_FACE_EXPRESSION2_CHEEK_PUFF_R_FB",
        "cheek_raise_l": "XR_FACE_EXPRESSION2_CHEEK_RAISER_L_FB",
        "cheek_raise_r": "XR_FACE_EXPRESSION2_CHEEK_RAISER_R_FB",
        "cheek_suck_l": "XR_FACE_EXPRESSION2_CHEEK_SUCK_L_FB",
        "cheek_suck_r": "XR_FACE_EXPRESSION2_CHEEK_SUCK_R_FB",
        
        # Jaw blendshapes
        "jaw_open": "XR_FACE_EXPRESSION2_JAW_DROP_FB",
        "jaw_l": "XR_FACE_EXPRESSION2_JAW_SIDEWAYS_LEFT_FB",
        "jaw_r": "XR_FACE_EXPRESSION2_JAW_SIDEWAYS_RIGHT_FB",
        "jaw_forward": "XR_FACE_EXPRESSION2_JAW_THRUST_FB",
        
        # Mouth blendshapes
        "mouth_smile_l": "XR_FACE_EXPRESSION2_LIP_CORNER_PULLER_L_FB",
        "mouth_smile_r": "XR_FACE_EXPRESSION2_LIP_CORNER_PULLER_R_FB",
        "mouth_frown_l": "XR_FACE_EXPRESSION2_LIP_CORNER_DEPRESSOR_L_FB",
        "mouth_frown_r": "XR_FACE_EXPRESSION2_LIP_CORNER_DEPRESSOR_R_FB",
        "mouth_l": "XR_FACE_EXPRESSION2_MOUTH_LEFT_FB",
        "mouth_r": "XR_FACE_EXPRESSION2_MOUTH_RIGHT_FB",
        "mouth_pucker_up_l": "XR_FACE_EXPRESSION2_LIP_PUCKER_L_FB",
        "mouth_pucker_up_r": "XR_FACE_EXPRESSION2_LIP_PUCKER_R_FB",
        "mouth_funnel_up_l": "XR_FACE_EXPRESSION2_LIP_FUNNELER_LB_FB",
        "mouth_funnel_up_r": "XR_FACE_EXPRESSION2_LIP_FUNNELER_RB_FB",
        "mouth_stretch_l": "XR_FACE_EXPRESSION2_LIP_STRETCHER_L_FB",
        "mouth_stretch_r": "XR_FACE_EXPRESSION2_LIP_STRETCHER_R_FB",
        "mouth_press_l": "XR_FACE_EXPRESSION2_LIP_PRESSOR_L_FB",
        "mouth_press_r": "XR_FACE_EXPRESSION2_LIP_PRESSOR_R_FB",
        "mouth_tighten_l": "XR_FACE_EXPRESSION2_LIP_TIGHTENER_L_FB",
        "mouth_tighten_r": "XR_FACE_EXPRESSION2_LIP_TIGHTENER_R_FB",
        "mouth_dimple_l": "XR_FACE_EXPRESSION2_DIMPLER_L_FB",
        "mouth_dimple_r": "XR_FACE_EXPRESSION2_DIMPLER_R_FB",
        
        # Nose blendshapes
        "nose_sneer_l": "XR_FACE_EXPRESSION2_NOSE_WRINKLER_L_FB",
        "nose_sneer_r": "XR_FACE_EXPRESSION2_NOSE_WRINKLER_R_FB",
    }
    
    # Create mappings for detected blendshapes
    mappings = []
    for blendshape in blendshapes:
        # Extract the meaningful part of the blendshape name
        # e.g., "CC_Base_Body_Eye_Blink_L" -> "eye_blink_l"
        name_parts = blendshape["name"].lower().split("_")
        
        # Try to reconstruct a standard name from the parts
        # Skip prefix parts like "cc", "base", "body"
        meaningful_parts = []
        skip_prefixes = ["cc", "base", "body", "eye"]  # "eye" prefix handled separately
        
        for part in name_parts:
            if part not in skip_prefixes:
                meaningful_parts.append(part)
        
        # Reconstruct the name
        if meaningful_parts:
            standardized_name = "_".join(meaningful_parts)
            
            # Check direct mapping first
            if standardized_name in cc_to_openxr_mapping:
                target = cc_to_openxr_mapping[standardized_name]
            else:
                # Try alternative patterns for eye-related shapes
                # Handle special case where "Eye" is part of the name
                if "eye" in name_parts and len(meaningful_parts) >= 2:
                    # Reconstruct with "eye" prefix
                    eye_name = "eye_" + "_".join(meaningful_parts)
                    if eye_name in cc_to_openxr_mapping:
                        target = cc_to_openxr_mapping[eye_name]
                    else:
                        continue
                else:
                    continue
            
            mapping_entry = {
                "id": _data_counter,
                "name": f"{blendshape['name']}_mapping",
                "source": blendshape["name"],
                "target": target,
                "mappingType": "blendshape"
            }
            mappings.append(mapping_entry)
            _data_counter += 1
    
    if not mappings:
        return None
        
    # Create AnimationLink according to ARF specification
    animation_link = {
        "id": _data_counter,
        "name": "OpenXR_Face_Tracking_Link",
        "animationStandard": OPENXR_FACIAL_URN,
        "version": "1.0",
        "mappings": mappings
    }
    _data_counter += 1
    
    return animation_link

def create_body_animation_link(skeleton_data, nodes_data, settings):
    """Create ARF-compliant AnimationLink for body tracking mappings"""
    if not settings.create_body_mapping or not skeleton_data:
        return None
        
    global _data_counter
    
    # Enhanced mapping for CC Base skeleton to OpenXR Body Tracking
    cc_to_openxr_body_mapping = {
        # Core body
        "CC_Base_BoneRoot": "XR_BODY_JOINT_ROOT_FB",
        "CC_Base_Hip": "XR_BODY_JOINT_HIPS_FB",
        "CC_Base_Pelvis": "XR_BODY_JOINT_HIPS_FB",
        "CC_Base_Spine01": "XR_BODY_JOINT_SPINE_LOWER_FB",
        "CC_Base_Spine02": "XR_BODY_JOINT_SPINE_MIDDLE_FB",
        "CC_Base_Spine03": "XR_BODY_JOINT_SPINE_UPPER_FB",
        "CC_Base_NeckTwist01": "XR_BODY_JOINT_NECK_FB",
        "CC_Base_Head": "XR_BODY_JOINT_HEAD_FB",
        
        # Left arm
        "CC_Base_L_Clavicle": "XR_BODY_JOINT_LEFT_SHOULDER_FB",
        "CC_Base_L_Upperarm": "XR_BODY_JOINT_LEFT_ARM_UPPER_FB",
        "CC_Base_L_Forearm": "XR_BODY_JOINT_LEFT_ARM_LOWER_FB",
        "CC_Base_L_Hand": "XR_BODY_JOINT_LEFT_HAND_WRIST_TWIST_FB",
        
        # Right arm
        "CC_Base_R_Clavicle": "XR_BODY_JOINT_RIGHT_SHOULDER_FB",
        "CC_Base_R_Upperarm": "XR_BODY_JOINT_RIGHT_ARM_UPPER_FB",
        "CC_Base_R_Forearm": "XR_BODY_JOINT_RIGHT_ARM_LOWER_FB",
        "CC_Base_R_Hand": "XR_BODY_JOINT_RIGHT_HAND_WRIST_TWIST_FB",
        
        # Left leg
        "CC_Base_L_Thigh": "XR_BODY_JOINT_LEFT_HIP_FB",
        "CC_Base_L_Calf": "XR_BODY_JOINT_LEFT_KNEE_FB",
        "CC_Base_L_Foot": "XR_BODY_JOINT_LEFT_ANKLE_FB",
        "CC_Base_L_ToeBase": "XR_BODY_JOINT_LEFT_FOOT_BALL_FB",
        
        # Right leg  
        "CC_Base_R_Thigh": "XR_BODY_JOINT_RIGHT_HIP_FB",
        "CC_Base_R_Calf": "XR_BODY_JOINT_RIGHT_KNEE_FB",
        "CC_Base_R_Foot": "XR_BODY_JOINT_RIGHT_ANKLE_FB",
        "CC_Base_R_ToeBase": "XR_BODY_JOINT_RIGHT_FOOT_BALL_FB",
        
        # Hands - left
        "CC_Base_L_Thumb1": "XR_BODY_JOINT_LEFT_HAND_THUMB_METACARPAL_FB",
        "CC_Base_L_Thumb2": "XR_BODY_JOINT_LEFT_HAND_THUMB_PROXIMAL_FB", 
        "CC_Base_L_Thumb3": "XR_BODY_JOINT_LEFT_HAND_THUMB_DISTAL_FB",
        "CC_Base_L_Index1": "XR_BODY_JOINT_LEFT_HAND_INDEX_PROXIMAL_FB",
        "CC_Base_L_Index2": "XR_BODY_JOINT_LEFT_HAND_INDEX_INTERMEDIATE_FB",
        "CC_Base_L_Index3": "XR_BODY_JOINT_LEFT_HAND_INDEX_DISTAL_FB",
        "CC_Base_L_Mid1": "XR_BODY_JOINT_LEFT_HAND_MIDDLE_PROXIMAL_FB",
        "CC_Base_L_Mid2": "XR_BODY_JOINT_LEFT_HAND_MIDDLE_INTERMEDIATE_FB",
        "CC_Base_L_Mid3": "XR_BODY_JOINT_LEFT_HAND_MIDDLE_DISTAL_FB",
        "CC_Base_L_Ring1": "XR_BODY_JOINT_LEFT_HAND_RING_PROXIMAL_FB",
        "CC_Base_L_Ring2": "XR_BODY_JOINT_LEFT_HAND_RING_INTERMEDIATE_FB",
        "CC_Base_L_Ring3": "XR_BODY_JOINT_LEFT_HAND_RING_DISTAL_FB",
        "CC_Base_L_Pinky1": "XR_BODY_JOINT_LEFT_HAND_LITTLE_PROXIMAL_FB",
        "CC_Base_L_Pinky2": "XR_BODY_JOINT_LEFT_HAND_LITTLE_INTERMEDIATE_FB",
        "CC_Base_L_Pinky3": "XR_BODY_JOINT_LEFT_HAND_LITTLE_DISTAL_FB",
        
        # Hands - right
        "CC_Base_R_Thumb1": "XR_BODY_JOINT_RIGHT_HAND_THUMB_METACARPAL_FB",
        "CC_Base_R_Thumb2": "XR_BODY_JOINT_RIGHT_HAND_THUMB_PROXIMAL_FB",
        "CC_Base_R_Thumb3": "XR_BODY_JOINT_RIGHT_HAND_THUMB_DISTAL_FB",
        "CC_Base_R_Index1": "XR_BODY_JOINT_RIGHT_HAND_INDEX_PROXIMAL_FB",
        "CC_Base_R_Index2": "XR_BODY_JOINT_RIGHT_HAND_INDEX_INTERMEDIATE_FB",
        "CC_Base_R_Index3": "XR_BODY_JOINT_RIGHT_HAND_INDEX_DISTAL_FB",
        "CC_Base_R_Mid1": "XR_BODY_JOINT_RIGHT_HAND_MIDDLE_PROXIMAL_FB",
        "CC_Base_R_Mid2": "XR_BODY_JOINT_RIGHT_HAND_MIDDLE_INTERMEDIATE_FB",
        "CC_Base_R_Mid3": "XR_BODY_JOINT_RIGHT_HAND_MIDDLE_DISTAL_FB",
        "CC_Base_R_Ring1": "XR_BODY_JOINT_RIGHT_HAND_RING_PROXIMAL_FB",
        "CC_Base_R_Ring2": "XR_BODY_JOINT_RIGHT_HAND_RING_INTERMEDIATE_FB",
        "CC_Base_R_Ring3": "XR_BODY_JOINT_RIGHT_HAND_RING_DISTAL_FB",
        "CC_Base_R_Pinky1": "XR_BODY_JOINT_RIGHT_HAND_LITTLE_PROXIMAL_FB",
        "CC_Base_R_Pinky2": "XR_BODY_JOINT_RIGHT_HAND_LITTLE_INTERMEDIATE_FB",
        "CC_Base_R_Pinky3": "XR_BODY_JOINT_RIGHT_HAND_LITTLE_DISTAL_FB",
    }
    
    # The skeleton data in ARF uses "joints" which are indices to nodes
    # We need to get the actual bone names from the nodes
    
    # Create mappings for detected bones
    mappings = []
    
    # Get joint indices from skeleton
    joint_indices = skeleton_data.get("joints", [])
    
    # Create mappings for each joint
    for joint_idx in joint_indices:
        if joint_idx < len(nodes_data):
            node = nodes_data[joint_idx]
            bone_name = node.get("name", "")
            
            # Check if this bone maps to an OpenXR body joint
            if bone_name in cc_to_openxr_body_mapping:
                mapping_entry = {
                    "id": _data_counter,
                    "name": f"{node['name']}_mapping",
                    "source": node["name"],
                    "target": cc_to_openxr_body_mapping[bone_name],
                    "mappingType": "bone"
                }
                mappings.append(mapping_entry)
                _data_counter += 1
    
    if not mappings:
        return None
        
    # Create AnimationLink according to ARF specification
    animation_link = {
        "id": _data_counter,
        "name": "OpenXR_Body_Tracking_Link",
        "animationStandard": OPENXR_BODY_URN,
        "version": "1.0",
        "mappings": mappings
    }
    _data_counter += 1
    
    return animation_link

def extract_blendshapes(mesh_obj, mesh_id=None):
    """Extract blend shapes (shape keys) from a mesh object."""
    global _blendshape_counter
    
    if not mesh_obj.data.shape_keys:
        return None, None
        
    # Find the basis shape key
    basis_key = mesh_obj.data.shape_keys.reference_key
    if not basis_key:
        return None, None
    
    # Create a blendshape set
    set_id = _blendshape_counter
    _blendshape_counter += 1
    # Define blendshape set according to ARF spec: use baseMesh (not basisMesh)
    blendshape_set = {
        "name": f"{mesh_obj.name}_blendshapes",
        "id": set_id,
        "shapes": [],
        # refer to the base mesh data id
        "baseMesh": mesh_id if mesh_id is not None else 0
    }
    
    # Process each shape key
    blendshape_data = []
    for key_block in mesh_obj.data.shape_keys.key_blocks:
        # Skip the basis shape
        if key_block == basis_key:
            continue
            
        # Generate unique ID for this blendshape
        shape_id = _blendshape_counter
        _blendshape_counter += 1
        
        # Add to the blendshape set
        blendshape_set["shapes"].append(shape_id)
        
        # Create the data entry
        data_entry = {
            "id": shape_id,
            "name": key_block.name,
            "type": "model/gltf-binary",
            "uri": f"blendshapes/{mesh_obj.name}_{key_block.name}.glb",
            "target": mesh_obj.name
        }
        
        # Try to map to OpenXR standard if possible
        normalized_name = key_block.name.lower().replace(" ", "_")
        if normalized_name in BLENDSHAPE_MAPPING:
            data_entry["mapping"] = BLENDSHAPE_MAPPING[normalized_name]
            
        blendshape_data.append(data_entry)
    
    return blendshape_set, blendshape_data

def export_blendshapes(mesh_obj, temp_dir, settings):
    """Export individual blendshapes as GLB files using custom exporter."""
    if not mesh_obj.data.shape_keys:
        return []
        
    print(f"\nExporting blendshapes for {mesh_obj.name}")
    
    # Create the blendshapes directory
    blendshapes_dir = os.path.join(temp_dir, "blendshapes")
    os.makedirs(blendshapes_dir, exist_ok=True)
    
    # Find the basis shape key
    basis_key = mesh_obj.data.shape_keys.reference_key
    if not basis_key:
        return []
    
    # Store original values to restore later
    original_values = {}
    for key_block in mesh_obj.data.shape_keys.key_blocks:
        original_values[key_block.name] = key_block.value
        key_block.value = 0.0  # Reset all to zero initially
    
    exported_blendshapes = []
    
    try:
        # First export the basis shape (mesh with no shape keys applied)
        basis_name = f"{mesh_obj.name}_Basis"
        basis_glb_path = os.path.join(blendshapes_dir, f"{basis_name}.glb")
        
        # Export with all shape keys at 0
        shape_values = {key_block.name: 0.0 for key_block in mesh_obj.data.shape_keys.key_blocks}
        if export_mesh_with_shape_key_applied(mesh_obj, shape_values, basis_glb_path):
            exported_blendshapes.append({
                "id": hash(f"{mesh_obj.name}_Basis") % 10000,
                "name": "Basis",
                "type": "model/gltf-binary",
                "uri": f"blendshapes/{basis_name}.glb"
            })
            print(f"Exported basis blendshape: {basis_name}")
            if os.path.exists(basis_glb_path):
                size_kb = os.path.getsize(basis_glb_path) / 1024
                print(f"  Size: {size_kb:.1f} KB")
        
        # Now export each blendshape individually
        for key_block in mesh_obj.data.shape_keys.key_blocks:
            if key_block == basis_key:
                continue  # Skip basis
            
            shape_name = f"{mesh_obj.name}_{key_block.name}"
            shape_glb_path = os.path.join(blendshapes_dir, f"{shape_name}.glb")
            
            # Export with only this shape key at full value
            shape_values = {kb.name: 0.0 for kb in mesh_obj.data.shape_keys.key_blocks}
            shape_values[key_block.name] = 1.0
            
            if export_mesh_with_shape_key_applied(mesh_obj, shape_values, shape_glb_path):
                exported_blendshapes.append({
                    "id": hash(f"{mesh_obj.name}_{key_block.name}") % 10000,
                    "name": key_block.name,
                    "type": "model/gltf-binary",
                    "uri": f"blendshapes/{shape_name}.glb"
                })
                print(f"Exported blendshape: {shape_name}")
                if os.path.exists(shape_glb_path):
                    size_kb = os.path.getsize(shape_glb_path) / 1024
                    print(f"  Size: {size_kb:.1f} KB")
            else:
                print(f"ERROR: Failed to export blendshape: {shape_name}")
                
    except Exception as e:
        print(f"ERROR exporting blendshapes: {str(e)}")
        if settings.debug_mode:
            import traceback
            traceback.print_exc()
    
    finally:
        # Restore original shape key values
        for key_name, value in original_values.items():
            if key_name in mesh_obj.data.shape_keys.key_blocks:
                mesh_obj.data.shape_keys.key_blocks[key_name].value = value
    
    return exported_blendshapes

def export_animations(armature_obj, temp_dir, settings):
    """Export animations for an armature."""
    global _data_counter
    
    if not armature_obj or not settings.export_animations:
        return []
    
    # Create animations directory
    animations_dir = os.path.join(temp_dir, "animations")
    os.makedirs(animations_dir, exist_ok=True)
    
    animation_data = []
    
    # Check for animations in the armature
    if not armature_obj.animation_data or not armature_obj.animation_data.action:
        print(f"No animations found for {armature_obj.name}")
        return animation_data
    
    print(f"Exporting animations for {armature_obj.name}")
    
    # Create a temporary scene for animation export
    temp_scene = bpy.data.scenes.new("ARFAnimExport")
    orig_scene = bpy.context.window.scene
    bpy.context.window.scene = temp_scene
    
    try:
        # Copy the armature for export
        temp_armature = armature_obj.copy()
        temp_armature.data = armature_obj.data.copy()
        temp_scene.collection.objects.link(temp_armature)

        # Make sure animation data is transferred
        if armature_obj.animation_data and armature_obj.animation_data.action:
            # If temp_armature has no animation_data, create it
            if not temp_armature.animation_data:
                temp_armature.animation_data_create()

            # Assign the action
            temp_armature.animation_data.action = armature_obj.animation_data.action
            action = temp_armature.animation_data.action
            anim_name = action.name if action else "unknown"
        else:
            print("No animation action found")
            return []

        # Select the armature
        temp_armature.select_set(True)
        temp_scene.view_layers[0].objects.active = temp_armature
        
        # Export the animation to GLB
        anim_path = os.path.join(animations_dir, f"{anim_name}.glb")
        # TODO: Implement animation export using custom GLB exporter
        print(f"WARNING: Animation export not yet implemented with custom GLB exporter")
        print(f"Skipping animation: {anim_name}")
        return []
        
        # Placeholder for when animation export is implemented
        if False and os.path.exists(anim_path):
            # Add to animation data
            anim_id = _data_counter
            _data_counter += 1
            animation_data.append({
                "id": anim_id,
                "name": anim_name,
                "type": "model/gltf-binary",
                "uri": f"animations/{anim_name}.glb",
                "target": armature_obj.name
            })
            print(f"Exported animation: {anim_name}")
        else:
            print(f"Failed to export animation: {anim_name}")
    
    except Exception as e:
        print(f"Error exporting animations: {str(e)}")
        if settings.debug_mode:
            import traceback
            traceback.print_exc()
    
    finally:
        # Clean up
        bpy.context.window.scene = orig_scene
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
    
    return animation_data

def create_lod(mesh_obj, lod_level, temp_dir, settings):
    """Create a lower level of detail for a mesh."""
    global _data_counter
    
    # Only implement if settings.export_lods is True
    if not settings.export_lods:
        return None
    
    print(f"Creating LOD {lod_level} for {mesh_obj.name}")
    
    # Create a temporary scene
    temp_scene = bpy.data.scenes.new("ARFLodScene")
    orig_scene = bpy.context.window.scene
    bpy.context.window.scene = temp_scene
    
    try:
        # Copy the mesh
        lod_obj = mesh_obj.copy()
        lod_obj.data = mesh_obj.data.copy()
        lod_name = f"{mesh_obj.name}_LOD{lod_level}"
        lod_obj.name = lod_name
        temp_scene.collection.objects.link(lod_obj)
        
        # Select the LOD object
        lod_obj.select_set(True)
        temp_scene.view_layers[0].objects.active = lod_obj
        
        # Apply a decimate modifier
        decimate = lod_obj.modifiers.new(name="ARFLodDecimate", type='DECIMATE')

        # Set ratio based on LOD level (1 = high, 2 = medium, 3 = low)
        if lod_level == 1:
            decimate.ratio = 0.8  # 20% reduction
        elif lod_level == 2:
            decimate.ratio = 0.5  # 50% reduction
        else:
            decimate.ratio = 0.2  # 80% reduction

        # Apply the modifier using a version-compatible approach
        try:
            # First try the newer API where we select the object first
            lod_obj.select_set(True)
            temp_scene.view_layers[0].objects.active = lod_obj
            bpy.ops.object.modifier_apply(modifier=decimate.name)
        except Exception as e:
            print(f"First attempt to apply modifier failed: {str(e)}, trying alternate method")
            try:
                # Try older API variant
                bpy.ops.object.modifier_apply({"object": lod_obj}, modifier=decimate.name)
            except Exception as e2:
                print(f"Second attempt to apply modifier failed: {str(e2)}, trying final method")
                # Last resort - try the 2.8+ API directly
                try:
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    mesh_eval = lod_obj.evaluated_get(depsgraph).data
                    lod_obj.modifiers.remove(decimate)
                    lod_obj.data = bpy.data.meshes.new_from_object(mesh_eval)
                except Exception as e3:
                    print(f"Failed to apply modifier through any method: {str(e3)}")
                    # Continue anyway as the glTF export might still work with unapplied modifier
        
        # Export the LOD mesh
        lod_dir = os.path.join(temp_dir, "lods")
        os.makedirs(lod_dir, exist_ok=True)
        
        lod_path = os.path.join(lod_dir, f"{lod_name}.glb")
        
        # Use custom GLB exporter
        export_success = False
        print("Using custom GLB exporter for LOD")
        try:
            # Export the decimated mesh
            export_success = export_mesh_to_glb_simple(lod_obj, lod_path, include_skin=False, armature_obj=None)
            if export_success:
                size_kb = os.path.getsize(lod_path) / 1024
                print(f"LOD export successful (custom exporter): {size_kb:.1f} KB")
            else:
                print("Custom LOD export failed")
        except Exception as e:
            print(f"LOD export error with custom exporter: {str(e)}")
            if settings.debug_mode:
                import traceback
                traceback.print_exc()
        
        # No fallback - custom exporter is required
        if not export_success:
            print("ERROR: Failed to export LOD with custom exporter")
            return None
        
        if export_success and os.path.exists(lod_path):
            lod_id = _data_counter
            _data_counter += 1
            return {
                "id": lod_id,
                "name": lod_name,
                "type": "model/gltf-binary",
                "uri": f"lods/{lod_name}.glb",
                "level": lod_level
            }
        else:
            print(f"Failed to export LOD {lod_level} for {mesh_obj.name}")
            return None
            
    except Exception as e:
        print(f"Error creating LOD: {str(e)}")
        if settings.debug_mode:
            import traceback
            traceback.print_exc()
        return None
        
    finally:
        # Clean up
        bpy.context.window.scene = orig_scene
        bpy.data.scenes.remove(temp_scene, do_unlink=True)

def organize_meshes_into_assets(context):
    """
    Organize selected meshes into individual assets based on their types.
    
    Body parts (body, head, eyes, teeth) are grouped together into a single "body" asset.
    Clothing, footwear, and accessories become individual assets.
    
    Returns:
        Dictionary mapping asset names to their components
    """
    import re
    assets = {}
    
    # Find all selected meshes and armatures
    meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
    
    # Define patterns for classification
    body_patterns = [
        r'body', r'skin', r'base', r'torso', r'chest', r'pelvis',
        r'abdomen', r'waist', r'hip', r'shoulder', r'arm', r'leg',
        r'hand', r'foot', r'finger', r'toe', r'neck', r'head',
        r'face', r'teeth', r'tongue', r'tear', r'occlusion',
        r'eye', r'iris', r'cornea', r'pupil', r'sclera', r'eyeball',
        r'eyelash', r'brow'
    ]
    
    clothing_patterns = [
        r'shirt', r'pants', r'dress', r'jacket', r'coat', r'suit',
        r'skirt', r'shorts', r'jeans', r'tshirt', r't-shirt', r'blouse',
        r'sweater', r'hoodie', r'vest', r'uniform', r'outfit', r'fit_shirt'
    ]
    
    footwear_patterns = [
        r'shoe', r'boot', r'sock', r'sandal', r'sneaker', r'heel',
        r'slipper', r'footwear', r'canvas_shoe'
    ]
    
    # Lists to collect meshes by type
    body_meshes = []
    individual_assets = []
    
    # Classify each mesh
    for mesh in meshes:
        name_lower = mesh.name.lower()
        # Remove common prefixes
        name_clean = re.sub(r'^(cc_|std_|default_|base_)', '', name_lower)
        
        # Check if it's a body part
        if any(re.search(pattern, name_clean) for pattern in body_patterns):
            body_meshes.append(mesh)
        elif any(re.search(pattern, name_clean) for pattern in clothing_patterns + footwear_patterns):
            # Clothing and footwear become individual assets
            individual_assets.append(mesh)
        else:
            # Unknown items also become individual assets
            individual_assets.append(mesh)
    
    # Create the body asset if there are body meshes
    if body_meshes:
        assets['body'] = {
            'name': 'body',
            'meshes': body_meshes,
            'armatures': armatures  # Body asset gets all armatures
        }
    
    # Create individual assets for clothing, footwear, etc.
    for mesh in individual_assets:
        # Use the mesh name as the asset name
        asset_name = mesh.name.lower()
        # Clean up common prefixes
        asset_name = re.sub(r'^(cc_|std_|default_|base_)', '', asset_name)
        
        assets[asset_name] = {
            'name': asset_name,
            'meshes': [mesh],
            'armatures': []  # Individual assets don't own armatures but can reference them
        }
    
    # If no specific organization was found, create a single asset
    if not assets and (meshes or armatures):
        assets['main_avatar'] = {
            'name': 'main_avatar',
            'meshes': meshes,
            'armatures': armatures
        }
    
    return assets

def organize_by_asset_type(context, temp_dir, settings):
    """Organize the export by individual assets with shared skeleton."""
    global _mesh_counter, _data_counter
    
    # This function will process the selection and organize by collections or naming
    
    # Reset component counters for clean export
    reset_component_counters()
    
    print("\nOrganizing assets...")
    
    # Gather data structures for the ARF format
    # Build ARF document with corrected preamble per ISO/IEC 23090-39
    arf_data = {
        "preamble": {
            "signature": ARF_SIGNATURE,
            "version": ARF_VERSION,
            # supportedAnimations keys must be arrays according to ARF spec
            "supportedAnimations": {
                "faceAnimations":      [ OPENXR_FACIAL_URN ],
                "bodyAnimations":      [ MPEG_BODY_URN ],
                "handAnimations":      [ MPEG_HAND_URN ],
                "landmarkAnimations":  [],
                "proprietaryAnimations": []
            }
        },
        "metadata": generate_metadata(),
        "structure": {
            "assets": []
        },
        "components": {
            "skeletons": [],
            "skins": [],
            "meshes": [],
            "nodes": [],
            "blendshapeSets": [],
            "animationLinks": []
        },
        "data": []
    }
    
    # Get multi-asset organization based on mesh classification
    collection_assets = organize_meshes_into_assets(context)
    
    if not collection_assets:
        # Fallback to single asset if no organization found
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        armature_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        collection_assets = {
            'main_avatar': {
                'name': 'main_avatar', 
                'meshes': mesh_objects,
                'armatures': armature_objects
            }
        }
    
    print(f"Found {len(collection_assets)} assets")
    for asset_name, asset_data in collection_assets.items():
        print(f"  {asset_name}: {len(asset_data['meshes'])} meshes, {len(asset_data['armatures'])} armatures")
    
    # Step 1: Process all armatures first (skeleton is shared across all assets)
    all_armatures = []
    skeleton_map = {}  # armature -> skeleton_id
    
    # Collect all armatures from all assets
    for asset_data in collection_assets.values():
        all_armatures.extend(asset_data['armatures'])
    
    # Remove duplicates
    all_armatures = list(set(all_armatures))
    
    # If no armatures are explicitly assigned, find them from meshes
    if not all_armatures:
        print("No armatures in assets, searching for armatures used by meshes...")
        armatures_from_meshes = set()
        for asset_data in collection_assets.values():
            for mesh in asset_data['meshes']:
                armature = find_armature_for_mesh(mesh)
                if armature:
                    armatures_from_meshes.add(armature)
        all_armatures = list(armatures_from_meshes)
        print(f"Found {len(all_armatures)} armatures from mesh modifiers")
    
    # Export skeletons
    for armature in all_armatures:
        if settings.export_skeletons:
            skeleton_data, node_data = get_skeleton_data(armature)
            if skeleton_data:
                arf_data["components"]["skeletons"].append(skeleton_data)
                arf_data["components"]["nodes"].extend(node_data)
                skeleton_map[armature] = skeleton_data["id"]
                print(f"Exported shared skeleton: {armature.name} (id: {skeleton_data['id']})")
    
    # Get list of all skeleton IDs for sharing
    shared_skeleton_ids = list(skeleton_map.values())
    
    # Step 2: Process each asset
    asset_id_counter = 0
    files_exported = []
    
    for asset_name, asset_data in collection_assets.items():
        print(f"\nProcessing asset: {asset_name}")
        
        mesh_objects = asset_data['meshes']
        armature_objects = asset_data['armatures']
        
        if not mesh_objects and not armature_objects:
            continue
            
        # Create asset structure
        asset = {
            "name": asset_name,
            "id": asset_id_counter,
            "lods": []
        }
        asset_id_counter += 1
        
        # If no meshes are found but armatures are selected, try to find meshes with armature modifiers
        if len(mesh_objects) == 0 and len(armature_objects) > 0:
            print("No meshes selected directly. Searching for meshes with armature modifiers...")
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    for modifier in obj.modifiers:
                        if modifier.type == 'ARMATURE' and modifier.object in armature_objects:
                            mesh_objects.append(obj)
                            print(f"Adding mesh {obj.name} linked to armature {modifier.object.name}")
            print(f"Found {len(mesh_objects)} additional meshes through armature relationships")
        
        # Map meshes to their armatures
        armature_mesh_map = {}
        for mesh in mesh_objects:
            armature = find_armature_for_mesh(mesh)
            if armature:
                if armature not in armature_mesh_map:
                    armature_mesh_map[armature] = []
                armature_mesh_map[armature].append(mesh)
                print(f"Mesh {mesh.name} is linked to armature {armature.name}")
            else:
                print(f"Mesh {mesh.name} has no armature")
        
        # Initialize LOD structures with shared skeletons
        base_lod = {
            "name": "high_quality",
            "skins": [],
            "meshes": [],
            "skeletons": shared_skeleton_ids.copy(),  # All assets share the same skeletons
            "blendshapeSets": []
        }
        medium_lod = {
            "name": "medium_quality", 
            "skins": [],
            "meshes": [],
            "skeletons": shared_skeleton_ids.copy(),
            "blendshapeSets": []
        }
        low_lod = {
            "name": "low_quality",
            "skins": [],
            "meshes": [],
            "skeletons": shared_skeleton_ids.copy(),
            "blendshapeSets": []
        }
        
        # Process all meshes in this asset
        for mesh in mesh_objects:
            # Find armature for this mesh
            armature = find_armature_for_mesh(mesh)
            
            # Export the main mesh
            mesh_data = export_mesh_to_glb(mesh, temp_dir, settings, armature)
            if mesh_data:
                files_exported.append(os.path.join(temp_dir, mesh_data["uri"]))
                # Use the actual mesh data ID for proper referencing
                mesh_id = mesh_data["id"]
                arf_data["data"].append(mesh_data)
                base_lod["meshes"].append(mesh_id)
                
                # Register in components (schema requires: name, id, path, data)
                arf_data["components"]["meshes"].append({
                    "name": mesh.name,
                    "id": mesh_id,
                    "path": f"meshes/{mesh.name}",  # Hierarchical path
                    "data": [len(arf_data["data"]) - 1]  # Reference to data item
                })
                
                # Handle skinning data for meshes bound to armatures
                if armature and settings.export_skeletons:
                    # Only create skin component if mesh actually has vertex weights
                    if has_vertex_weights(mesh, armature):
                        # Create skin component using shared skeleton
                        if armature in skeleton_map:
                            skeleton_id = skeleton_map[armature]
                            skin_data = extract_skin_data(mesh, armature, mesh_id, skeleton_id)
                            if skin_data:
                                # Export weights (tensor or GLB)
                                weight_data = export_skin_weights(mesh, armature, temp_dir, settings)
                                
                                if weight_data:
                                    if isinstance(weight_data, list):
                                        # Tensor format - reference Data items by their IDs
                                        weight_ids = []
                                        for entry in weight_data:
                                            files_exported.append(os.path.join(temp_dir, entry["uri"]))
                                            arf_data["data"].append(entry)
                                            weight_ids.append(entry["id"])
                                        skin_data["weights"] = weight_ids
                                    else:
                                        # GLB format
                                        files_exported.append(os.path.join(temp_dir, weight_data["uri"]))
                                        arf_data["data"].append(weight_data)
                                        skin_data["weights"] = [weight_data["id"]]
                                    
                                    # Add skin component
                                    arf_data["components"]["skins"].append(skin_data)
                                    skin_index = len(arf_data["components"]["skins"]) - 1
                                    base_lod["skins"].append(skin_index)
                                    medium_lod["skins"].append(skin_index)
                                    low_lod["skins"].append(skin_index)
                                    
                                    print(f"Added skin component for {mesh.name}")
                        else:
                            print(f"Warning: Mesh {mesh.name} has armature {armature.name} but skeleton not found in skeleton_map")
                    else:
                        print(f"Mesh {mesh.name} has no vertex weights")
                
                # Export blendshapes if present
                if settings.export_blendshapes and mesh.data.shape_keys:
                    # Extract blendshape data
                    blendshape_set, blendshape_entries = extract_blendshapes(mesh, mesh_id)
                    if blendshape_set:
                        # register blendshapeSet component and reference in all LODs
                        arf_data["components"]["blendshapeSets"].append(blendshape_set)
                        for lod in (base_lod, medium_lod, low_lod):
                            lod["blendshapeSets"].append(blendshape_set["id"])
                        
                        # Export individual blendshapes
                        for bs_entry in export_blendshapes(mesh, temp_dir, settings):
                            if bs_entry:
                                files_exported.append(os.path.join(temp_dir, bs_entry["uri"]))
                                arf_data["data"].append(bs_entry)
                
                # Create LODs if enabled
                if settings.export_lods:
                    # Medium quality LOD
                    medium_lod_data = create_lod(mesh, 2, temp_dir, settings)
                    if medium_lod_data:
                        files_exported.append(os.path.join(temp_dir, medium_lod_data["uri"]))
                        arf_data["data"].append(medium_lod_data)
                        # reference in medium LOD
                        medium_lod["meshes"].append(medium_lod_data["id"])
                    # Low quality LOD
                    low_lod_data = create_lod(mesh, 3, temp_dir, settings)
                    if low_lod_data:
                        files_exported.append(os.path.join(temp_dir, low_lod_data["uri"]))
                        arf_data["data"].append(low_lod_data)
                        # reference in low LOD
                        low_lod["meshes"].append(low_lod_data["id"])
        
        # Add LODs to asset and asset to structure
        asset["lods"].extend([base_lod, medium_lod, low_lod])
        arf_data["structure"]["assets"].append(asset)
        
    # Export animations (associated with skeleton, not specific assets)
    if settings.export_animations:
        for armature in all_armatures:
            animation_data = export_animations(armature, temp_dir, settings)
            for anim_entry in animation_data:
                files_exported.append(os.path.join(temp_dir, anim_entry["uri"]))
                arf_data["data"].append(anim_entry)
    
    # Note: All meshes are now processed within their assets, so no standalone processing needed
    
    if False:  # Disabled - standalone meshes are handled in asset processing
        # Create a default asset for standalone meshes
        standalone_asset = {
            "name": "standalone_meshes",
            "id": asset_id_counter,
            "lods": [{
                "name": "default",
                "skins": [],
                "meshes": [],
                "skeletons": [],
                "blendshapeSets": []
            }]
        }
        asset_id_counter += 1
        
        for mesh in mesh_objects:
            # Check if this mesh has an armature that was already processed (only if armature was selected)
            processed_meshes = [m for arm in armature_objects for m in armature_mesh_map.get(arm, [])]
            if mesh not in processed_meshes:
                print(f"Processing standalone mesh: {mesh.name}")
                
                # Get the armature if it exists but wasn't in the selected armatures
                standalone_armature = find_armature_for_mesh(mesh)
                if standalone_armature:
                    print(f"  Found unselected armature: {standalone_armature.name}")
                
                # Export standalone mesh
                mesh_data = export_mesh_to_glb(mesh, temp_dir, settings, standalone_armature)
                if mesh_data:
                    files_exported.append(os.path.join(temp_dir, mesh_data["uri"]))
                    # Use the actual mesh data ID for proper referencing
                    mesh_id = mesh_data["id"]
                    arf_data["data"].append(mesh_data)
                    standalone_asset["lods"][0]["meshes"].append(mesh_id)
                    
                    # Register in components (schema requires: name, id, path, data)
                    arf_data["components"]["meshes"].append({
                        "name": mesh.name,
                        "id": mesh_id,
                        "path": f"meshes/{mesh.name}",  # Hierarchical path
                        "data": [len(arf_data["data"]) - 1]  # Reference to data item
                    })
                    
                    # Handle skinning data if there's an armature
                    if standalone_armature and settings.export_skeletons:
                        # Only process if mesh has vertex weights
                        if has_vertex_weights(mesh, standalone_armature):
                            # First, make sure we have the skeleton data
                            skeleton_data, node_data = get_skeleton_data(standalone_armature)
                            if skeleton_data:
                                # Add skeleton if not already added
                                if not any(s["id"] == skeleton_data["id"] for s in arf_data["components"]["skeletons"]):
                                    arf_data["components"]["skeletons"].append(skeleton_data)
                                    arf_data["components"]["nodes"].extend(node_data)
                                    standalone_asset["lods"][0]["skeletons"].append(skeleton_data["id"])
                                
                                # Create skin component
                                skin_data = extract_skin_data(mesh, standalone_armature, mesh_id, skeleton_data["id"])
                                if skin_data:
                                    # Export weights (tensor or GLB)
                                    weight_data = export_skin_weights(mesh, standalone_armature, temp_dir, settings)
                                    
                                    if weight_data:
                                        if isinstance(weight_data, list):
                                            # Tensor format - reference Data items by their IDs
                                            weight_ids = []
                                            for entry in weight_data:
                                                files_exported.append(os.path.join(temp_dir, entry["uri"]))
                                                arf_data["data"].append(entry)
                                                weight_ids.append(entry["id"])
                                            skin_data["weights"] = weight_ids
                                        else:
                                            # GLB format returns single entry
                                            files_exported.append(os.path.join(temp_dir, weight_data["uri"]))
                                            arf_data["data"].append(weight_data)
                                            skin_data["weights"] = [weight_data["id"]]
                                        
                                        # Add skin component to ARF document
                                        arf_data["components"]["skins"].append(skin_data)
                                        
                                        # Reference skin in LOD entry using array index
                                        skin_index = len(arf_data["components"]["skins"]) - 1
                                        standalone_asset["lods"][0]["skins"].append(skin_index)
                                        
                                        print(f"Added skin component for standalone mesh {mesh.name}")
                        else:
                            print(f"Standalone mesh {mesh.name} has no vertex weights, exporting as regular mesh")
                    
                    # Handle blendshapes for standalone meshes
                    if settings.export_blendshapes and mesh.data.shape_keys:
                        blendshape_set, blendshape_entries = extract_blendshapes(mesh, mesh_id)
                        if blendshape_set:
                            arf_data["components"]["blendshapeSets"].append(blendshape_set)
                            standalone_asset["lods"][0]["blendshapeSets"].append(blendshape_set["id"])
                            
                            # Export individual blendshapes
                            for bs_entry in export_blendshapes(mesh, temp_dir, settings):
                                if bs_entry:
                                    files_exported.append(os.path.join(temp_dir, bs_entry["uri"]))
                                    arf_data["data"].append(bs_entry)
        
        # Only add if we processed any standalone meshes
        if standalone_asset["lods"][0]["meshes"]:
            arf_data["structure"]["assets"].append(standalone_asset)
    
    # Create ARF-compliant AnimationLinks if enabled
    if settings.create_face_mapping or settings.create_body_mapping:
        print("\nCreating XR AnimationLinks...")
        
        # Create face tracking AnimationLink if we have blendshapes
        if settings.create_face_mapping and arf_data["components"]["blendshapeSets"]:
            # Collect all blendshape names from the data array
            # Look for individual blendshape GLB files, not blendshapeSet entries
            blendshape_data_items = []
            for data_item in arf_data["data"]:
                # Check if this is a blendshape GLB file
                if (data_item.get("uri", "").startswith("blendshapes/") and 
                    data_item.get("uri", "").endswith(".glb") and
                    not data_item.get("name", "").endswith("_Basis")):  # Skip basis meshes
                    blendshape_data_items.append(data_item)
            
            if blendshape_data_items:
                face_animation_link = create_face_animation_link(blendshape_data_items, settings)
                if face_animation_link:
                    arf_data["components"]["animationLinks"].append(face_animation_link)
                    print(f"✅ Created face tracking AnimationLink with {len(face_animation_link['mappings'])} mappings")
                else:
                    print("⚠️  No face tracking mappings found for existing blendshapes")
        
        # Create body tracking AnimationLink if we have skeletons
        if settings.create_body_mapping and arf_data["components"]["skeletons"]:
            # Get nodes data to pass to the body animation link creator
            nodes_data = arf_data["components"].get("nodes", [])
            for skeleton in arf_data["components"]["skeletons"]:
                body_animation_link = create_body_animation_link(skeleton, nodes_data, settings)
                if body_animation_link:
                    arf_data["components"]["animationLinks"].append(body_animation_link)
                    print(f"✅ Created body tracking AnimationLink with {len(body_animation_link['mappings'])} mappings")
                    break  # Only create one body animation link
    
    # Print warning if no files were exported
    if not files_exported:
        print("WARNING: No asset files were exported. The ZIP will only contain arf.json.")
    else:
        print(f"Successfully exported {len(files_exported)} asset files:")
        for exported_file in files_exported:
            print(f"  - {os.path.basename(exported_file)}")
    
    return arf_data, files_exported

def generate_metadata():
    """Generate ARF-compliant metadata."""
    # Check if there's metadata from the GUI
    if hasattr(bpy.context.scene, 'arf_export_settings'):
        settings = bpy.context.scene.arf_export_settings
        if hasattr(settings, 'avatar_metadata'):
            metadata = settings.avatar_metadata
            # Use metadata integration to generate compliant structure
            try:
                from addons.arf_exporter.core.metadata_integration import MetadataIntegration
                meta_integration = MetadataIntegration(metadata)
                raw_metadata = meta_integration.generate_arf_metadata()
                # Convert to compliant format
                return validate_metadata_compliance(raw_metadata)
            except:
                pass
    
    # Fallback to basic compliant metadata
    return {
        "name": bpy.path.basename(bpy.data.filepath).split('.')[0] or "untitled",
        "id": str(uuid.uuid4()),
        "age": 25,  # Integer as required by schema
        "gender": "unspecified"  # String as required by schema
    }

def find_armature_for_mesh(obj):
    """Find the armature associated with a mesh through modifiers."""
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE' and modifier.object:
            return modifier.object
    return None

def export_arf_zip(context, filepath, settings):
    """Export the ARF container as a zip file."""

    # Get the Blender filename to use for the export
    blend_filename = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if not blend_filename:
        blend_filename = "untitled"

    # Set filepath to use the Blender filename
    output_dir = os.path.dirname(filepath)
    filepath = os.path.join(output_dir, f"{blend_filename}.zip")

    print(f"Using output file: {filepath}")

    # Create temporary directory
    temp_dir = os.path.join(os.path.dirname(filepath), "arf_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Generate the ARF data structure by organizing assets
        arf_data, files_exported = organize_by_asset_type(context, temp_dir, settings)
        
        # Apply ARF compliance fixes
        arf_data = fix_arf_compliance(arf_data)
        arf_data = remove_non_compliant_fields(arf_data)
        
        # Write ARF JSON
        arf_json_path = os.path.join(temp_dir, "arf.json")
        with open(arf_json_path, "w") as f:
            json.dump(arf_data, f, indent=4)
        
        # Log export progress
        print("\n=== ARF Export Progress ===")
        print(f"Export path: {filepath}")
        print(f"Scale factor: {settings.scale}")
        
        # Count selected objects by type
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        armature_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        print(f"\nExporting {len(mesh_objects)} meshes and {len(armature_objects)} armatures")
        
        # List all generated files
        print("\nGenerated files:")
        total_size = 0
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, temp_dir)
                size = os.path.getsize(file_path)
                total_size += size
                size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
                print(f"- {rel_path:<50} {size_str:>10}")
        
        # Check if any files were exported
        if len(files_exported) == 0:
            print("\nWARNING: No mesh files were exported. The ZIP will only contain arf.json.")
            print("This may be due to errors in the export process or missing glTF exporter.")
        
        # Create ZIP archive - filepath is already guaranteed to have .zip extension
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from temp directory with proper relative paths
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, temp_dir)
                    print(f"Adding to ZIP: {rel_path}")
                    zipf.write(file_path, rel_path)
        
        # Verify and report ZIP contents
        print("\nVerifying ARF container contents:")
        with zipfile.ZipFile(filepath, 'r') as zipf:
            zip_size = os.path.getsize(filepath)
            zip_size_str = f"{zip_size/1024:.1f} KB" if zip_size < 1024*1024 else f"{zip_size/(1024*1024):.1f} MB"
            print(f"Container size: {zip_size_str}")
            print("Included files:")
            for info in sorted(zipf.infolist(), key=lambda x: x.filename):
                size_str = f"{info.file_size/1024:.1f} KB" if info.file_size < 1024*1024 else f"{info.file_size/(1024*1024):.1f} MB"
                compression = (1 - info.compress_size/info.file_size) * 100 if info.file_size > 0 else 0
                print(f"- {info.filename:<50} {size_str:>10} (compressed: {compression:.1f}%)")

            # Extra verification - check that ALL exported files made it into the ZIP
            zip_files = set(zipf.namelist())
            expected_files = set(os.path.relpath(f, temp_dir).replace('\\', '/') for f in files_exported)
            expected_files.add("arf.json")  # Add the JSON manifest

            missing_files = expected_files - zip_files
            if missing_files:
                print("\nWARNING: Some expected files are missing from the ZIP:")
                for missing in missing_files:
                    print(f"  - {missing}")

        print(f"\nARF export completed successfully!")
        print(f"Output: {os.path.abspath(filepath)}")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nERROR during export: {str(e)}")
        if settings.debug_mode:
            import traceback
            traceback.print_exc()
        raise
    
    finally:
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except Exception as e:
                        print(f"WARNING: Could not remove file {file}: {str(e)}")
                for dir in dirs:
                    try:
                        os.rmdir(os.path.join(root, dir))
                    except Exception as e:
                        print(f"WARNING: Could not remove directory {dir}: {str(e)}")
            try:
                os.rmdir(temp_dir)
            except Exception as e:
                print(f"WARNING: Could not remove temporary directory: {str(e)}")

class ExportARF(bpy.types.Operator, ExportHelper):
    """Export selected objects to ARF format"""
    bl_idname = "export_scene.arf"
    bl_label = "Export ARF"
    filename_ext = ".zip"

    filter_glob: StringProperty(
        default="*.zip",
        options={'HIDDEN'}
    )

    object_name: StringProperty(
        name="Object Name",
        description="Name of the object to export (leave empty to use selected objects)",
        default=""
    )

    scale: FloatProperty(
        name="Scale",
        description="Scale factor for export",
        default=1.0,
        min=0.001,
        max=1000.0
    )

    export_animations: BoolProperty(
        name="Export Animations",
        description="Export animations from selected armatures",
        default=True
    )

    export_blendshapes: BoolProperty(
        name="Export Blendshapes",
        description="Export shape keys as ARF blendshapes",
        default=True
    )

    export_skeletons: BoolProperty(
        name="Export Skeletons",
        description="Export armatures as ARF skeletons",
        default=True
    )

    export_textures: BoolProperty(
        name="Export Textures",
        description="Export materials and textures",
        default=True
    )

    export_lods: BoolProperty(
        name="Generate LODs",
        description="Generate lower quality levels of detail",
        default=True
    )

    optimize_mesh: BoolProperty(
        name="Optimize Mesh",
        description="Optimize exported meshes (Draco compression removed)",
        default=False
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply non-armature modifiers before export",
        default=True
    )

    debug_mode: BoolProperty(
        name="Debug Mode",
        description="Enable detailed error logging",
        default=True
    )

    metadata_age: FloatProperty(
        name="Avatar Age",
        description="Age of the avatar character",
        default=25,
        min=0,
        max=150
    )

    metadata_gender: EnumProperty(
        name="Avatar Gender",
        description="Gender of the avatar character",
        items=[
            ('male', "Male", ""),
            ('female', "Female", ""),
            ('neutral', "Neutral", "")
        ],
        default='neutral'
    )
    
    # Tensor weight options
    use_tensor_weights: BoolProperty(
        name="Use Tensor Weights",
        description="Export skin weights as tensor data instead of GLB",
        default=True,
    )
    
    tensor_precision: EnumProperty(
        name="Tensor Precision",
        description="Data type for tensor weights",
        items=(
            ('float32', "Float32", "32-bit floating point (highest precision)"),
            ('float16', "Float16", "16-bit floating point (balanced)"),
            ('uint16', "UInt16", "16-bit unsigned integer (compact)"),
            ('uint8', "UInt8", "8-bit unsigned integer (most compact)"),
        ),
        default='float32',
    )

    def report_export_stats(self, context):
        """Report statistics about the exported objects"""
        if self.object_name.strip():
            # If using object name parameter
            obj = bpy.data.objects.get(self.object_name)
            if obj:
                obj_type = obj.type.lower()
                return f"Exporting object: {self.object_name} ({obj_type})"
            else:
                return f"Object '{self.object_name}' not found"
        else:
            # Using selected objects
            mesh_count = len([obj for obj in context.selected_objects if obj.type == 'MESH'])
            armature_count = len([obj for obj in context.selected_objects if obj.type == 'ARMATURE'])

            stats = []
            if mesh_count:
                stats.append(f"{mesh_count} mesh{'es' if mesh_count > 1 else ''}")
            if armature_count:
                stats.append(f"{armature_count} armature{'s' if armature_count > 1 else ''}")

            return f"Selected objects: {', '.join(stats)}"

    def execute(self, context):
        # Create a custom context for export
        export_context = context.copy()
        original_selection = None

        # Handle object_name if provided
        if self.object_name.strip():
            # Store original selection
            original_selection = [obj for obj in context.selected_objects]

            # Deselect all objects
            for obj in context.selected_objects:
                obj.select_set(False)

            # Find and select the named object
            obj = bpy.data.objects.get(self.object_name)
            if obj:
                obj.select_set(True)
                # Try to set active object
                if context.view_layer.objects.active is not None:
                    context.view_layer.objects.active = obj
            else:
                self.report({'ERROR'}, f"Object '{self.object_name}' not found")
                return {'CANCELLED'}

        # Check if any objects are selected
        if not context.selected_objects:
            self.report({'ERROR'}, "No objects selected for export")
            return {'CANCELLED'}

        # Log export start
        self.report({'INFO'}, f"Starting ARF export: {self.report_export_stats(context)}")

        try:
            settings = ARFExportSettings()
            settings.scale = self.scale
            settings.export_animations = self.export_animations
            settings.export_blendshapes = self.export_blendshapes
            settings.export_skeletons = self.export_skeletons
            settings.export_textures = self.export_textures
            settings.export_lods = self.export_lods
            settings.optimize_mesh = self.optimize_mesh
            settings.apply_modifiers = self.apply_modifiers
            settings.debug_mode = self.debug_mode
            
            # Tensor settings
            settings.use_tensor_weights = self.use_tensor_weights
            settings.tensor_precision = self.tensor_precision

            # Perform the export
            export_arf_zip(context, self.filepath, settings)

            # Show success message with statistics
            self.report({'INFO'}, f"ARF export successful: {os.path.basename(self.filepath)}")

            # Create popup content with file path
            filepath_for_popup = self.filepath

            def draw_popup(self_popup, context):
                self_popup.layout.label(text="ARF Export Completed Successfully!")
                self_popup.layout.label(text=f"File: {os.path.basename(filepath_for_popup)}")
                self_popup.layout.label(text=self.report_export_stats(context))

            # Skip popup in background mode
            if not bpy.app.background:
                bpy.context.window_manager.popup_menu(draw_popup, title="Export Complete", icon='FILE_TICK')
            else:
                print("Export completed successfully! (popup suppressed in background mode)")

            # Restore original selection if we modified it
            if original_selection is not None:
                # Deselect the current selection
                for obj in context.selected_objects:
                    obj.select_set(False)

                # Restore original selection
                for obj in original_selection:
                    if obj:
                        obj.select_set(True)

            return {'FINISHED'}

        except Exception as e:
            # Log any errors that occur
            self.report({'ERROR'}, f"Export failed: {str(e)}")

            # Restore original selection if we modified it
            if original_selection is not None:
                # Deselect the current selection
                for obj in context.selected_objects:
                    obj.select_set(False)

                # Restore original selection
                for obj in original_selection:
                    if obj:
                        obj.select_set(True)

            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout

        # General settings
        box = layout.box()
        box.label(text="General Settings", icon='SETTINGS')
        box.prop(self, "object_name")
        box.prop(self, "scale")

        # Export options
        box = layout.box()
        box.label(text="Export Options", icon='EXPORT')
        box.prop(self, "export_animations")
        box.prop(self, "export_blendshapes")
        box.prop(self, "export_skeletons")
        box.prop(self, "export_textures")
        box.prop(self, "export_lods")

        # Optimization options
        box = layout.box()
        box.label(text="Optimization", icon='MOD_SMOOTH')
        box.prop(self, "optimize_mesh")
        box.prop(self, "apply_modifiers")

        # Debug options
        box = layout.box()
        box.label(text="Debug", icon='CONSOLE')
        box.prop(self, "debug_mode")

        # Metadata
        box = layout.box()
        box.label(text="Avatar Metadata", icon='INFO')
        box.prop(self, "metadata_age")
        box.prop(self, "metadata_gender")

def menu_func_export(self, context):
    self.layout.operator(ExportARF.bl_idname, text="Avatar Representation Format (.zip)")

def register():
    bpy.utils.register_class(ExportARF)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ExportARF)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
    
    # Support command-line execution
    if bpy.app.background:
        import argparse
        
        def parse_args():
            """Parse command line arguments after the -- separator"""
            try:
                separator_index = sys.argv.index('--')
                args = sys.argv[separator_index + 1:]
            except ValueError:
                args = []
            
            parser = argparse.ArgumentParser(description='Export Blender scene to ARF format')
            parser.add_argument('--output', '-o', default='output.zip', help='Output ARF file path')
            parser.add_argument('--scale', type=float, default=1.0, help='Export scale')
            parser.add_argument('--no-animations', action='store_true', help='Skip animation export')
            parser.add_argument('--no-blendshapes', action='store_true', help='Skip blendshape export')
            parser.add_argument('--no-textures', action='store_true', help='Skip texture export')
            parser.add_argument('--no-lods', action='store_true', help='Skip LOD generation')
            parser.add_argument('--debug', action='store_true', help='Enable debug mode')
            
            return parser.parse_args(args)
        
        # Parse arguments
        args = parse_args()
        
        print("=" * 70)
        print("ARF Exporter - Fixed Version with Custom GLB Export")
        print("=" * 70)
        print(f"Output file: {args.output}")
        print(f"Scale: {args.scale}")
        print("✓ Custom GLB exporter loaded - mesh isolation enabled")
        print()
        
        # Ensure we have an absolute path
        output_path = os.path.abspath(args.output)
        
        # Select all mesh objects and armatures if nothing is selected
        if not bpy.context.selected_objects:
            print("No objects selected, selecting all mesh objects and armatures...")
            bpy.ops.object.select_all(action='DESELECT')
            for obj in bpy.context.scene.objects:
                if obj.type in ['MESH', 'ARMATURE']:
                    obj.select_set(True)
            
            # Set active object
            if bpy.context.selected_objects:
                bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        
        print(f"Selected {len(bpy.context.selected_objects)} objects for export")
        print()
        
        # Execute the export
        try:
            result = bpy.ops.export_scene.arf(
                filepath=output_path,
                scale=args.scale,
                export_animations=not args.no_animations,
                export_blendshapes=not args.no_blendshapes,
                export_textures=not args.no_textures,
                export_lods=not args.no_lods,
                debug_mode=args.debug
            )
            
            if result == {'FINISHED'}:
                print()
                print("=" * 70)
                print("✅ Export completed successfully!")
                print(f"Output file: {output_path}")
                
                # Get file info
                if os.path.exists(output_path):
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    print(f"File size: {size_mb:.1f} MB")
                print("=" * 70)
            else:
                print("❌ Export failed!")
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ Export error: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
