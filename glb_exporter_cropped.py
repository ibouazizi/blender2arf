#!/usr/bin/env python3
"""
Blender to GLB exporter with proper texture cropping support.
This implementation properly integrates the texture cropping from gltf2arf.
"""

import bpy
import numpy as np
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from io import BytesIO

# Import the base GLB exporter
from glb_exporter import (
    SimpleGLBGenerator,
    convert_blender_to_gltf_coords,
    convert_blender_to_gltf_normal,
    extract_texture_from_node,
    encode_image_to_buffer,
    _add_texture_to_glb
)

# Import texture cropping utilities
try:
    from texture_cropper import TextureCropper, UVBoundsCalculator
    CROPPING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Texture cropping not available: {e}")
    CROPPING_AVAILABLE = False


def _add_texture_to_glb_cropped(generator, original_image, cropped_data, mime_type):
    """Add a cropped texture to the GLB generator."""
    # Add to buffer
    padding = (4 - (generator.buffer_data.tell() % 4)) % 4
    if padding:
        generator.buffer_data.write(b'\x00' * padding)
        
    buffer_offset = generator.buffer_data.tell()
    generator.buffer_data.write(cropped_data)
    buffer_length = len(cropped_data)
    
    # Create buffer view
    buffer_view_idx = len(generator.buffer_views)
    generator.buffer_views.append({
        "buffer": 0,
        "byteOffset": buffer_offset,
        "byteLength": buffer_length
    })
    
    # Add image
    image_idx = len(generator.images)
    generator.images.append({
        "bufferView": buffer_view_idx,
        "mimeType": mime_type,
        "name": f"{original_image.name}_cropped"
    })
    
    # Add sampler
    sampler_idx = len(generator.samplers)
    generator.samplers.append({
        "magFilter": 9729,
        "minFilter": 9987,
        "wrapS": 10497,
        "wrapT": 10497
    })
    
    # Add texture
    texture_idx = len(generator.textures)
    generator.textures.append({
        "source": image_idx,
        "sampler": sampler_idx,
        "name": f"{original_image.name}_cropped"
    })
    
    return texture_idx


def export_mesh_to_glb_with_texture_cropping(
    mesh_obj: bpy.types.Object, 
    output_path: str,
    scale: float = 1.0,
    crop_textures: bool = True,
    include_skin: bool = False,
    armature_obj: Optional[bpy.types.Object] = None
) -> bool:
    """
    Export a mesh to GLB with proper texture cropping support.
    
    Args:
        mesh_obj: Blender mesh object to export
        output_path: Output GLB file path
        scale: Scale factor for the mesh
        crop_textures: Whether to crop textures based on UV usage
        include_skin: Whether to include skinning data
        armature_obj: Armature object for skinning
        
    Returns:
        True if successful, False otherwise
    """
    if not CROPPING_AVAILABLE or not crop_textures:
        # Fall back to simple export
        from blender_to_glb_simple import export_mesh_to_glb_simple
        return export_mesh_to_glb_simple(
            mesh_obj, output_path, 
            include_skin=include_skin, 
            armature_obj=armature_obj, 
            scale=scale
        )
    
    try:
        mesh = mesh_obj.data
        mesh.calc_loop_triangles()
        
        # Get the evaluated mesh
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        
        # Process mesh data by material
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
            
            # Process each vertex in the triangle
            for i in range(3):
                loop_idx = tri.loops[i]
                vert_idx = eval_mesh.loops[loop_idx].vertex_index
                vert = eval_mesh.vertices[vert_idx]
                
                # Get UV for this loop
                uv = [0.0, 0.0]
                if eval_mesh.uv_layers.active:
                    uv = list(eval_mesh.uv_layers.active.data[loop_idx].uv)
                
                # Create unique vertex key
                vert_key = (vert_idx, tuple(uv))
                
                if vert_key not in prim_data['vertex_map']:
                    # Add new vertex
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
        generator = SimpleGLBGenerator()
        
        # Process materials and textures
        materials_data = []
        texture_data_map = {}  # Maps texture index to actual image data
        
        for idx, mat_slot in enumerate(mesh_obj.material_slots):
            if mat_slot.material:
                mat = mat_slot.material
                
                mat_data = {
                    'name': mat.name,
                    'pbrMetallicRoughness': {},
                    'alphaMode': 'OPAQUE',
                    'doubleSided': True
                }
                
                # Extract textures from material
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            # Base color
                            base_color = node.inputs['Base Color'].default_value
                            mat_data['pbrMetallicRoughness']['baseColorFactor'] = [
                                base_color[0], base_color[1], base_color[2], base_color[3]
                            ]
                            
                            # Base color texture
                            base_color_image = extract_texture_from_node(node, 'Base Color')
                            if base_color_image:
                                # Store texture data for cropping
                                tex_idx = len(texture_data_map)
                                image_data, mime_type = encode_image_to_buffer(base_color_image)
                                if image_data:
                                    texture_data_map[tex_idx] = {
                                        'image': base_color_image,
                                        'data': image_data,
                                        'mime_type': mime_type
                                    }
                                    mat_data['pbrMetallicRoughness']['baseColorTexture'] = {
                                        'index': tex_idx,
                                        'texCoord': 0
                                    }
                            
                            # Metallic/Roughness
                            mat_data['pbrMetallicRoughness']['metallicFactor'] = node.inputs['Metallic'].default_value
                            mat_data['pbrMetallicRoughness']['roughnessFactor'] = node.inputs['Roughness'].default_value
                            break
                else:
                    # Fallback for non-node materials
                    mat_data['pbrMetallicRoughness']['baseColorFactor'] = [
                        mat.diffuse_color[0], mat.diffuse_color[1],
                        mat.diffuse_color[2], mat.diffuse_color[3]
                    ]
                    mat_data['pbrMetallicRoughness']['metallicFactor'] = mat.metallic
                    mat_data['pbrMetallicRoughness']['roughnessFactor'] = mat.roughness
                
                materials_data.append(mat_data)
        
        # Process primitives with texture cropping
        final_primitives = []
        texture_index_remap = {}  # Maps old texture indices to new ones
        
        for mat_idx, prim_data in sorted(material_primitives.items()):
            if not prim_data['vertices']:
                continue
            
            # Create primitive in format expected by TextureCropper
            primitive = {
                'attributes': {
                    'POSITION': np.array(prim_data['vertices'], dtype=np.float32),
                    'NORMAL': np.array(prim_data['normals'], dtype=np.float32),
                    'TEXCOORD_0': np.array(prim_data['uvs'], dtype=np.float32)
                },
                'indices': np.array(prim_data['indices'], dtype=np.uint32),
                'material': mat_idx
            }
            
            # Apply texture cropping if we have textures for this material
            if mat_idx < len(materials_data) and crop_textures:
                material = materials_data[mat_idx]
                pbr = material.get('pbrMetallicRoughness', {})
                
                if 'baseColorTexture' in pbr:
                    tex_idx = pbr['baseColorTexture']['index']
                    if tex_idx in texture_data_map:
                        # Calculate UV bounds for this primitive
                        uv_data = primitive['attributes']['TEXCOORD_0']
                        calculator = UVBoundsCalculator()
                        u_min, v_min, u_max, v_max = calculator.calculate_bounds(uv_data)
                        
                        print(f"DEBUG: UV bounds for material {mat_idx}: u=[{u_min:.3f}, {u_max:.3f}], v=[{v_min:.3f}, {v_max:.3f}]")
                        
                        # Check if texture is tiled
                        is_tiled = u_min < -0.01 or u_max > 1.01 or v_min < -0.01 or v_max > 1.01
                        
                        if not is_tiled:
                            # Crop the texture
                            try:
                                from PIL import Image
                                
                                # Get texture data
                                tex_data = texture_data_map[tex_idx]
                                image_bytes = tex_data['data']
                                
                                # Crop texture
                                cropped_image, pixel_bounds = TextureCropper.crop_texture(
                                    image_bytes,
                                    (u_min, v_min, u_max, v_max),
                                    pixel_padding=2,
                                    min_size=16
                                )
                                
                                # Get original image size
                                original_image = Image.open(BytesIO(image_bytes))
                                original_size = original_image.size
                                
                                # Check if cropping is worth it
                                # 1. Cropped area < 90% of original
                                # 2. Results in a smaller power-of-2 texture
                                original_area = original_size[0] * original_size[1]
                                cropped_area = cropped_image.size[0] * cropped_image.size[1]
                                area_ratio = cropped_area / original_area if original_area > 0 else 1.0
                                
                                # Check if dimensions are power-of-2
                                def is_power_of_2(n):
                                    return n > 0 and (n & (n - 1)) == 0
                                
                                is_valid_power_of_2 = is_power_of_2(cropped_image.size[0]) and is_power_of_2(cropped_image.size[1])
                                
                                # Check if it's actually smaller than original in at least one dimension
                                is_smaller = cropped_image.size[0] < original_size[0] or cropped_image.size[1] < original_size[1]
                                
                                if area_ratio < 0.9 and is_valid_power_of_2 and is_smaller:  # Only crop if all conditions met
                                    # Remap UV coordinates
                                    remapped_uvs = TextureCropper.remap_uv_coordinates(
                                        uv_data,
                                        (u_min, v_min, u_max, v_max),
                                        original_size,
                                        pixel_bounds
                                    )
                                    
                                    # Update primitive UVs
                                    primitive['attributes']['TEXCOORD_0'] = remapped_uvs.astype(np.float32)
                                    
                                    # Save cropped texture in the same format as original
                                    cropped_buffer = BytesIO()
                                    # Determine format from original mime type
                                    original_mime = tex_data.get('mime_type', 'image/png')
                                    if 'jpeg' in original_mime or 'jpg' in original_mime:
                                        cropped_image.save(cropped_buffer, format='JPEG', quality=95)
                                        cropped_mime = 'image/jpeg'
                                    else:
                                        cropped_image.save(cropped_buffer, format='PNG')
                                        cropped_mime = 'image/png'
                                    cropped_data = cropped_buffer.getvalue()
                                    
                                    # Add cropped texture to generator
                                    if tex_idx not in texture_index_remap:
                                        new_tex_idx = _add_texture_to_glb(
                                            generator, 
                                            tex_data['image'],
                                            uv_bounds=(u_min, v_min, u_max, v_max),
                                            original_size=original_size
                                        )
                                        texture_index_remap[tex_idx] = new_tex_idx
                                    
                                        # For cropped textures, we need to add them properly
                                        # Remove the old texture and add the cropped one
                                        generator.textures.pop()
                                        generator.images.pop()
                                        generator.samplers.pop()
                                        
                                        # Add cropped texture as new texture
                                        cropped_tex_idx = _add_texture_to_glb_cropped(
                                            generator,
                                            tex_data['image'],
                                            cropped_data,
                                            cropped_mime
                                        )
                                        texture_index_remap[tex_idx] = cropped_tex_idx
                                    
                                    # Calculate savings
                                    savings = TextureCropper.calculate_texture_savings(
                                        original_size, cropped_image.size
                                    )
                                    print(f"INFO: Cropped texture {tex_idx}: {original_size} -> {cropped_image.size} ({savings['reduction_percent']:.1f}% reduction)")
                                else:
                                    # Not worth cropping, use original texture
                                    skip_reason = []
                                    if area_ratio >= 0.9:
                                        skip_reason.append(f"only {(1-area_ratio)*100:.1f}% reduction")
                                    if not is_valid_power_of_2:
                                        skip_reason.append(f"would result in non-power-of-2 dimensions ({cropped_image.size[0]}x{cropped_image.size[1]})")
                                    if not is_smaller:
                                        skip_reason.append("no dimension reduction")
                                    print(f"INFO: Texture cropping skipped ({', '.join(skip_reason)})")
                                    if tex_idx not in texture_index_remap:
                                        new_tex_idx = _add_texture_to_glb(generator, tex_data['image'])
                                        texture_index_remap[tex_idx] = new_tex_idx
                                
                            except Exception as e:
                                print(f"WARNING: Texture cropping failed: {e}")
                                # Fall back to original texture
                                if tex_idx not in texture_index_remap:
                                    new_tex_idx = _add_texture_to_glb(generator, tex_data['image'])
                                    texture_index_remap[tex_idx] = new_tex_idx
                        else:
                            # Don't crop tiled textures
                            print(f"WARNING: Texture atlas or tiled texture detected. Skipping cropping.")
                            if tex_idx not in texture_index_remap:
                                new_tex_idx = _add_texture_to_glb(generator, texture_data_map[tex_idx]['image'])
                                texture_index_remap[tex_idx] = new_tex_idx
            
            final_primitives.append(primitive)
        
        # Update material texture indices with remapped values
        for mat_data in materials_data:
            pbr = mat_data.get('pbrMetallicRoughness', {})
            if 'baseColorTexture' in pbr:
                old_idx = pbr['baseColorTexture']['index']
                if old_idx in texture_index_remap:
                    pbr['baseColorTexture']['index'] = texture_index_remap[old_idx]
        
        # Create final mesh data
        mesh_data = {
            'name': mesh_obj.name,
            'primitives': final_primitives
        }
        
        # Generate GLB
        glb_data = generator.create_glb(mesh_data, materials_data)
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        print(f"Exported {mesh_obj.name} to {output_path} with texture cropping")
        return True
        
    except Exception as e:
        print(f"Error exporting mesh with texture cropping: {str(e)}")
        import traceback
        traceback.print_exc()
        return False