#!/usr/bin/env python3
"""
Advanced mesh processing for Blender with proper UV handling and texture cropping.
"""

import bpy
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

from uv_bounds_calculator import UVBoundsCalculator
from texture_cropper import TextureCropper


class MeshProcessorAdvanced:
    """Advanced mesh processor with UV bounds calculation and texture cropping."""
    
    @staticmethod
    def extract_mesh_data_per_material(mesh_obj: bpy.types.Object, scale: float = 1.0) -> Dict[int, Dict[str, Any]]:
        """
        Extract mesh data grouped by material with proper UV handling.
        
        Returns:
            Dictionary mapping material index to mesh data
        """
        mesh = mesh_obj.data
        mesh.calc_loop_triangles()
        
        # Get the evaluated mesh (with modifiers applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        
        # Dictionary to store data per material
        material_data = defaultdict(lambda: {
            'vertices': [],
            'normals': [],
            'uvs': [],
            'indices': [],
            'vertex_map': {},  # Original vertex index -> new vertex index
            'uv_bounds': None
        })
        
        # Process each triangle
        for tri in eval_mesh.loop_triangles:
            mat_idx = tri.material_index
            mat_data = material_data[mat_idx]
            
            triangle_indices = []
            
            for loop_idx in tri.loop_indices:
                vert_idx = eval_mesh.loops[loop_idx].vertex_index
                vert = eval_mesh.vertices[vert_idx]
                
                # Get UV for this loop
                uv = [0.0, 0.0]
                if eval_mesh.uv_layers.active:
                    uv = list(eval_mesh.uv_layers.active.data[loop_idx].uv)
                
                # Create unique vertex key (vertex index + UV)
                # This ensures vertices with different UVs are treated as separate
                vert_key = (vert_idx, tuple(uv))
                
                if vert_key not in mat_data['vertex_map']:
                    # Add new vertex
                    new_idx = len(mat_data['vertices'])
                    mat_data['vertex_map'][vert_key] = new_idx
                    
                    # Apply scale and coordinate conversion
                    from blender_to_glb_simple import convert_blender_to_gltf_coords, convert_blender_to_gltf_normal
                    scaled_pos = [coord * scale for coord in vert.co]
                    converted_pos = convert_blender_to_gltf_coords(scaled_pos)
                    converted_normal = convert_blender_to_gltf_normal(list(vert.normal))
                    
                    mat_data['vertices'].append(converted_pos)
                    mat_data['normals'].append(converted_normal)
                    mat_data['uvs'].append(uv)
                
                triangle_indices.append(mat_data['vertex_map'][vert_key])
            
            mat_data['indices'].extend(triangle_indices)
        
        # Convert to numpy arrays and calculate UV bounds
        result = {}
        for mat_idx, mat_data in material_data.items():
            if mat_data['vertices']:  # Only process if there are vertices
                vertices_array = np.array(mat_data['vertices'], dtype=np.float32)
                normals_array = np.array(mat_data['normals'], dtype=np.float32)
                uvs_array = np.array(mat_data['uvs'], dtype=np.float32)
                indices_array = np.array(mat_data['indices'], dtype=np.uint32)
                
                # Calculate UV bounds for this material
                uv_bounds = None
                if len(uvs_array) > 0:
                    uv_bounds = UVBoundsCalculator.calculate_bounds_with_padding(uvs_array, padding=0.01)
                
                result[mat_idx] = {
                    'attributes': {
                        'POSITION': vertices_array,
                        'NORMAL': normals_array,
                        'TEXCOORD_0': uvs_array
                    },
                    'indices': indices_array,
                    'uv_bounds': uv_bounds,
                    'material': mat_idx
                }
        
        return result
    
    @staticmethod
    def process_texture_with_cropping(
        image: bpy.types.Image,
        uv_bounds: Tuple[float, float, float, float],
        enable_cropping: bool = True
    ) -> Tuple[bytes, Optional[Tuple[int, int, int, int]], Tuple[int, int], str]:
        """
        Process a texture with optional cropping based on UV bounds.
        
        Returns:
            Tuple of (image_data, pixel_bounds, original_size, mime_type)
        """
        # Get original image data
        from blender_to_glb_simple import encode_image_to_buffer
        image_data, mime_type = encode_image_to_buffer(image)
        
        if not image_data:
            return None, None, (0, 0), "image/png"
        
        original_size = (image.size[0], image.size[1])
        
        if not enable_cropping or uv_bounds is None:
            # No cropping, return original
            return image_data, None, original_size, mime_type
        
        # Check if UV bounds indicate we can crop
        min_u, min_v, max_u, max_v = uv_bounds
        
        # Don't crop if UVs use most of the texture
        if (max_u - min_u) > 0.9 and (max_v - min_v) > 0.9:
            print(f"Texture {image.name} uses most of UV space, skipping crop")
            return image_data, None, original_size, mime_type
        
        # Check for tiled textures
        if UVBoundsCalculator.check_if_tiled(uv_bounds):
            print(f"Texture {image.name} appears to be tiled, skipping crop")
            return image_data, None, original_size, mime_type
        
        # Crop the texture
        try:
            cropped_data, pixel_bounds, new_mime_type = TextureCropper.crop_texture(
                image_data, uv_bounds, pixel_padding=2, min_size=16
            )
            
            # Calculate savings
            from PIL import Image
            from io import BytesIO
            cropped_img = Image.open(BytesIO(cropped_data))
            cropped_size = cropped_img.size
            
            savings = TextureCropper.calculate_texture_savings(original_size, cropped_size)
            if savings['reduction_percent'] > 10:  # Only use cropped if significant savings
                print(f"Cropped texture {image.name}: {original_size} -> {cropped_size} "
                      f"({savings['reduction_percent']:.1f}% reduction)")
                return cropped_data, pixel_bounds, original_size, new_mime_type
            else:
                print(f"Texture {image.name} crop savings too small ({savings['reduction_percent']:.1f}%), using original")
                return image_data, None, original_size, mime_type
                
        except Exception as e:
            print(f"Failed to crop texture {image.name}: {str(e)}")
            return image_data, None, original_size, mime_type
    
    @staticmethod
    def remap_uvs_for_cropped_texture(
        uvs: np.ndarray,
        pixel_bounds: Tuple[int, int, int, int],
        original_size: Tuple[int, int]
    ) -> np.ndarray:
        """Remap UV coordinates for a cropped texture."""
        # Use the texture cropper's remap function
        # Note: We don't need the original UV bounds since we're remapping based on pixel bounds
        return TextureCropper.remap_uv_coordinates(
            uvs,
            (0, 0, 1, 1),  # Original UV bounds (full texture)
            original_size,
            pixel_bounds
        )