#!/usr/bin/env python3
"""
External texture manager for ARF exports.
Handles texture deduplication and external file export.
"""

import os
import hashlib
import shutil
from typing import Dict, Tuple, Set
from pathlib import Path

class ExternalTextureManager:
    """Manages external texture files for GLB exports with asset-based organization."""
    
    def __init__(self, output_dir: str):
        """Initialize texture manager with output directory."""
        self.output_dir = Path(output_dir)
        self.textures_dir = self.output_dir / "meshes" / "textures"
        self.texture_registry = {}  # hash -> (filename, path)
        self.asset_texture_sets = {}  # asset_name -> {hash -> (filename, relative_uri)}
        self.texture_counter = 0
        
        # Create textures directory inside meshes folder
        self.textures_dir.mkdir(parents=True, exist_ok=True)
        
    def register_texture(self, image_data: bytes, original_name: str, mime_type: str, asset_name: str = None) -> Tuple[str, str]:
        """
        Register a texture and get its external file path.
        
        Args:
            image_data: Raw image data
            original_name: Original texture name
            mime_type: MIME type of the image
            asset_name: Name of the asset this texture belongs to
        
        Returns:
            Tuple of (filename, relative_uri_path)
        """
        # Calculate hash for deduplication
        texture_hash = hashlib.sha256(image_data).hexdigest()[:16]
        
        # If asset_name is provided, check asset-specific registry first
        if asset_name:
            if asset_name not in self.asset_texture_sets:
                self.asset_texture_sets[asset_name] = {}
            
            asset_registry = self.asset_texture_sets[asset_name]
            if texture_hash in asset_registry:
                return asset_registry[texture_hash]
        
        # Check global registry for cross-asset sharing
        if texture_hash in self.texture_registry:
            result = self.texture_registry[texture_hash]
            # Also add to asset registry if asset_name provided
            if asset_name:
                self.asset_texture_sets[asset_name][texture_hash] = result
            return result
        
        # Determine file extension from MIME type
        ext_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png', 
            'image/webp': '.webp',
            'image/tiff': '.tiff'
        }
        
        extension = ext_map.get(mime_type, '.jpg')
        
        # Clean up original name for filename
        clean_name = original_name.replace('_Diffuse', '').replace('_diffuse', '')
        clean_name = ''.join(c for c in clean_name if c.isalnum() or c in '-_')
        
        # Generate unique filename with asset prefix if provided
        if asset_name:
            clean_asset = ''.join(c for c in asset_name if c.isalnum() or c in '-_')
            filename = f"{clean_asset}_{clean_name}_{texture_hash}{extension}"
        else:
            filename = f"{clean_name}_{texture_hash}{extension}"
            
        file_path = self.textures_dir / filename
        
        # Write texture file
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Calculate relative URI path (textures is now inside meshes folder)
        relative_uri = f"textures/{filename}"
        
        # Store in both global and asset-specific registries
        result = (filename, relative_uri)
        self.texture_registry[texture_hash] = result
        if asset_name:
            self.asset_texture_sets[asset_name][texture_hash] = result
        
        # Texture exported successfully (verbose logging removed)
        
        return result
    
    def get_texture_stats(self) -> Dict[str, any]:
        """Get statistics about exported textures."""
        total_files = len(self.texture_registry)
        total_size = 0
        
        for filename, _ in self.texture_registry.values():
            file_path = self.textures_dir / filename
            if file_path.exists():
                total_size += file_path.stat().st_size
        
        # Asset-specific stats
        asset_stats = {}
        for asset_name, asset_registry in self.asset_texture_sets.items():
            asset_stats[asset_name] = {
                'texture_count': len(asset_registry),
                'textures': list(asset_registry.values())
            }
        
        return {
            'total_files': total_files,
            'total_size_kb': total_size / 1024,
            'textures_dir': str(self.textures_dir.relative_to(self.output_dir)),  # Show relative path
            'files': list(self.texture_registry.values()),
            'assets': asset_stats
        }
    
    def cleanup_unused_textures(self, used_textures: Set[str]):
        """Remove texture files that are no longer referenced."""
        for file_path in self.textures_dir.glob("*"):
            if file_path.is_file() and file_path.name not in used_textures:
                print(f"Removing unused texture: {file_path.name}")
                file_path.unlink()


class TextureSet:
    """Represents a set of related textures (diffuse, normal, metallic, etc.)"""
    
    def __init__(self, base_name: str):
        self.base_name = base_name
        self.textures = {}  # type -> (image_data, mime_type)
        
    def add_texture(self, texture_type: str, image_data: bytes, mime_type: str):
        """Add a texture of specific type to this set."""
        self.textures[texture_type] = (image_data, mime_type)
        
    def export_to_manager(self, manager: ExternalTextureManager, asset_name: str = None) -> Dict[str, str]:
        """Export all textures in this set and return URI mappings."""
        uri_map = {}
        
        for tex_type, (image_data, mime_type) in self.textures.items():
            original_name = f"{self.base_name}_{tex_type}"
            filename, relative_uri = manager.register_texture(image_data, original_name, mime_type, asset_name)
            uri_map[tex_type] = relative_uri
            
        return uri_map


def create_texture_set_from_material(material, object_name: str) -> TextureSet:
    """Create a TextureSet from a Blender material."""
    texture_set = TextureSet(f"{object_name}_{material.name}")
    
    if not material.use_nodes:
        return texture_set
        
    # Find principled BSDF node
    principled_node = None
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_node = node
            break
            
    if not principled_node:
        return texture_set
    
    # Extract different texture types
    texture_inputs = {
        'diffuse': 'Base Color',
        'normal': 'Normal', 
        'metallic': 'Metallic',
        'roughness': 'Roughness',
        'emission': 'Emission'
    }
    
    for tex_type, input_name in texture_inputs.items():
        if input_name in principled_node.inputs:
            socket = principled_node.inputs[input_name]
            if socket.is_linked:
                for link in socket.links:
                    from_node = link.from_node
                    if from_node.type == 'TEX_IMAGE' and from_node.image:
                        image = from_node.image
                        
                        # Get image data
                        from glb_exporter import encode_image_to_buffer
                        try:
                            image_data, mime_type = encode_image_to_buffer(image)
                            if image_data:
                                texture_set.add_texture(tex_type, image_data, mime_type)
                        except Exception as e:
                            print(f"Warning: Could not export {tex_type} texture for {material.name}: {e}")
    
    return texture_set