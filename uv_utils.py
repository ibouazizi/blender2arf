#!/usr/bin/env python3
"""
UV coordinate utilities for Blender to glTF conversion.
"""

import math

def convert_blender_uv_to_gltf(blender_u, blender_v):
    """
    Convert UV coordinates from Blender's coordinate system to glTF's.
    
    Blender: Origin at bottom-left (0,0), V increases upward
    glTF: Origin at top-left (0,0), V increases downward
    
    For texture atlases, we need to flip within each tile to preserve
    the texture orientation while maintaining the atlas layout.
    
    Args:
        blender_u: U coordinate from Blender
        blender_v: V coordinate from Blender
        
    Returns:
        tuple: (gltf_u, gltf_v)
    """
    # U coordinate remains the same
    gltf_u = blender_u
    
    # For V coordinate, we need to flip it
    # In texture atlases, each tile needs to be flipped independently
    
    # For simple case without texture atlas (V in [0,1])
    if 0 <= blender_v <= 1:
        gltf_v = 1.0 - blender_v
    else:
        # For texture atlas, we need to be more careful
        # The issue is that in a texture atlas, each "tile" has its own coordinate space
        # that needs to be flipped independently
        
        # Get the tile index and fractional part
        if blender_v >= 0:
            tile = int(blender_v)
            frac = blender_v - tile
        else:
            tile = int(blender_v) - 1  # For negative, we need to adjust
            frac = blender_v - tile
        
        # In texture atlases, the tiles are usually arranged vertically
        # Tile 0: V = [0, 1] -> Body
        # Tile 1: V = [1, 2] -> Head
        # etc.
        
        # When we flip, we need to maintain the tile arrangement
        # For a coordinate like 1.2 (tile 1, 20% from bottom of tile):
        # It should become 1.8 (tile 1, 80% from top of tile)
        
        flipped_frac = 1.0 - frac
        gltf_v = tile + flipped_frac
    
    return gltf_u, gltf_v


def test_uv_conversion():
    """Test UV conversion with various cases."""
    test_cases = [
        # Standard UVs within [0,1]
        (0.0, 0.0, "Bottom-left corner"),
        (1.0, 0.0, "Bottom-right corner"),
        (0.0, 1.0, "Top-left corner"),
        (1.0, 1.0, "Top-right corner"),
        (0.5, 0.5, "Center"),
        
        # Texture atlas UVs
        (0.5, 1.5, "Atlas tile 1"),
        (0.5, 2.5, "Atlas tile 2"),
        (1.5, 0.5, "Atlas adjacent tile"),
        
        # Edge cases
        (0.0, 2.0, "Exact tile boundary"),
        (-0.5, 0.5, "Negative U"),
        (0.5, -0.5, "Negative V"),
    ]
    
    print("UV Conversion Test Cases")
    print("=" * 60)
    print(f"{'Blender UV':<20} {'glTF UV':<20} {'Description':<20}")
    print("-" * 60)
    
    for u, v, desc in test_cases:
        gltf_u, gltf_v = convert_blender_uv_to_gltf(u, v)
        print(f"({u:6.2f}, {v:6.2f}){'':<8} ({gltf_u:6.2f}, {gltf_v:6.2f}){'':<8} {desc}")


if __name__ == "__main__":
    test_uv_conversion()