"""
Local texture cropping implementation without external dependencies
"""

import numpy as np
from PIL import Image
from typing import Dict, Tuple, Optional, Union
import io


class TextureCropper:
    """Handles texture cropping and UV coordinate remapping."""
    
    @staticmethod
    def crop_texture(
        image: Union[Image.Image, bytes],
        uv_bounds: Tuple[float, float, float, float],
        pixel_padding: int = 2,
        min_size: int = 16
    ) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
        """
        Crop a texture based on UV bounds with dimensions aligned to multiples of 16.
        """
        # Convert bytes to PIL Image if needed
        if isinstance(image, bytes):
            image = Image.open(io.BytesIO(image))
            
        width, height = image.size
        min_u, min_v, max_u, max_v = uv_bounds
        
        # Handle tiled textures
        if min_u < 0 or max_u > 1 or min_v < 0 or max_v > 1:
            print(f"WARNING: Tiled texture detected (UV bounds: {uv_bounds}). Cropping to [0,1] range.")
            min_u = max(0.0, min_u)
            max_u = min(1.0, max_u)
            min_v = max(0.0, min_v)
            max_v = min(1.0, max_v)
        
        # Convert UV to pixel coordinates
        # Note: V coordinate is flipped in UV space (0 is bottom, 1 is top)
        x_min = int(min_u * width)
        x_max = int(max_u * width)
        y_min = int((1.0 - max_v) * height)  # Flip V
        y_max = int((1.0 - min_v) * height)  # Flip V
        
        # Add pixel padding
        x_min = max(0, x_min - pixel_padding)
        x_max = min(width, x_max + pixel_padding)
        y_min = max(0, y_min - pixel_padding)
        y_max = min(height, y_max + pixel_padding)
        
        # Calculate dimensions
        crop_width = x_max - x_min
        crop_height = y_max - y_min
        
        # Align to power of 2 for better GPU compatibility
        def next_power_of_2(value):
            """Find the next power of 2 greater than or equal to value"""
            if value <= 0:
                return 1
            # If already a power of 2, return it
            if (value & (value - 1)) == 0:
                return value
            # Find next power of 2
            power = 1
            while power < value:
                power *= 2
            return power
        
        def prev_power_of_2(value):
            """Find the previous power of 2 less than or equal to value"""
            if value <= 0:
                return 1
            # Find the highest bit set
            power = 1
            while power * 2 <= value:
                power *= 2
            return power
        
        # Find the best power-of-2 dimensions
        # Try both rounding up and down to see which wastes less space
        width_up = next_power_of_2(crop_width)
        height_up = next_power_of_2(crop_height)
        width_down = prev_power_of_2(crop_width)
        height_down = prev_power_of_2(crop_height)
        
        # Calculate waste for both options
        waste_up = (width_up * height_up) - (crop_width * crop_height)
        waste_down = (crop_width * crop_height) - (width_down * height_down)
        
        # Choose the option that wastes less pixels, but ensure we don't crop too much
        if waste_down < waste_up and width_down >= crop_width * 0.8 and height_down >= crop_height * 0.8:
            new_width = width_down
            new_height = height_down
        else:
            new_width = width_up
            new_height = height_up
        
        # Ensure minimum size
        new_width = max(new_width, min_size)
        new_height = max(new_height, min_size)
        
        # Center the crop if we need to expand
        if new_width > crop_width:
            expand = (new_width - crop_width) // 2
            x_min = max(0, x_min - expand)
            x_max = min(width, x_min + new_width)
            # Adjust if we hit the edge
            if x_max - x_min < new_width:
                x_min = max(0, x_max - new_width)
                
        if new_height > crop_height:
            expand = (new_height - crop_height) // 2
            y_min = max(0, y_min - expand)
            y_max = min(height, y_min + new_height)
            # Adjust if we hit the edge
            if y_max - y_min < new_height:
                y_min = max(0, y_max - new_height)
        
        # Final bounds check
        x_max = x_min + new_width
        y_max = y_min + new_height
        
        # Ensure we don't exceed image bounds
        if x_max > width:
            x_max = width
            x_min = max(0, width - new_width)
        if y_max > height:
            y_max = height
            y_min = max(0, height - new_height)
            
        pixel_bounds = (x_min, y_min, x_max, y_max)
        
        # Crop the image
        cropped = image.crop(pixel_bounds)
        
        print(f"DEBUG: Cropped texture from {width}x{height} to {cropped.width}x{cropped.height} (power-of-2)")
        
        return cropped, pixel_bounds
    
    @staticmethod
    def remap_uv_coordinates(
        uv_data: np.ndarray,
        original_bounds: Tuple[float, float, float, float],
        image_size: Tuple[int, int],
        crop_pixel_bounds: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """
        Remap UV coordinates from original texture space to cropped texture space.
        """
        if uv_data.ndim == 1:
            uv_data = uv_data.reshape(-1, 2)
            
        remapped = uv_data.copy()
        width, height = image_size
        x_min, y_min, x_max, y_max = crop_pixel_bounds
        
        # Calculate the UV offset and scale based on pixel crop
        u_offset = x_min / width
        v_offset = 1.0 - (y_max / height)  # Flip for UV coordinate system
        u_scale = (x_max - x_min) / width
        v_scale = (y_max - y_min) / height
        
        # Remap UV coordinates
        # new_u = (old_u - u_offset) / u_scale
        # new_v = (old_v - v_offset) / v_scale
        remapped[:, 0] = (remapped[:, 0] - u_offset) / u_scale
        remapped[:, 1] = (remapped[:, 1] - v_offset) / v_scale
        
        # Clamp to [0, 1] to handle floating point precision issues
        remapped = np.clip(remapped, 0.0, 1.0)
        
        return remapped
    
    @staticmethod
    def calculate_texture_savings(
        original_size: Tuple[int, int],
        cropped_size: Tuple[int, int]
    ) -> Dict[str, float]:
        """Calculate memory savings from texture cropping."""
        original_pixels = original_size[0] * original_size[1]
        cropped_pixels = cropped_size[0] * cropped_size[1]
        
        return {
            'original_pixels': original_pixels,
            'cropped_pixels': cropped_pixels,
            'pixel_reduction': original_pixels - cropped_pixels,
            'reduction_percent': (1.0 - cropped_pixels / original_pixels) * 100 if original_pixels > 0 else 0,
            'size_ratio': cropped_pixels / original_pixels if original_pixels > 0 else 1.0
        }


class UVBoundsCalculator:
    """Calculate UV coordinate bounds for texture cropping."""
    
    @staticmethod
    def calculate_bounds(uv_data: np.ndarray, padding: float = 0.0) -> Tuple[float, float, float, float]:
        """
        Calculate the bounding box of UV coordinates.
        
        Args:
            uv_data: UV coordinates (Nx2 array)
            padding: Additional padding in UV space (0-1)
            
        Returns:
            (min_u, min_v, max_u, max_v)
        """
        if uv_data.size == 0:
            return (0.0, 0.0, 1.0, 1.0)
            
        if uv_data.ndim == 1:
            uv_data = uv_data.reshape(-1, 2)
            
        min_u = float(np.min(uv_data[:, 0]))
        max_u = float(np.max(uv_data[:, 0]))
        min_v = float(np.min(uv_data[:, 1]))
        max_v = float(np.max(uv_data[:, 1]))
        
        # Add padding
        if padding > 0:
            u_range = max_u - min_u
            v_range = max_v - min_v
            
            min_u -= padding * u_range
            max_u += padding * u_range
            min_v -= padding * v_range
            max_v += padding * v_range
        
        return (min_u, min_v, max_u, max_v)
    
    @staticmethod
    def calculate_bounds_with_padding(
        uv_data: np.ndarray, 
        uv_padding: float = 0.01,
        pixel_padding: int = 2,
        image_size: Tuple[int, int] = (1024, 1024)
    ) -> Tuple[float, float, float, float]:
        """
        Calculate UV bounds with both UV-space and pixel-space padding.
        """
        # Get base bounds with UV padding
        bounds = UVBoundsCalculator.calculate_bounds(uv_data, uv_padding)
        
        # Convert pixel padding to UV space
        width, height = image_size
        pixel_u_padding = pixel_padding / width
        pixel_v_padding = pixel_padding / height
        
        # Apply pixel padding
        min_u, min_v, max_u, max_v = bounds
        min_u -= pixel_u_padding
        max_u += pixel_u_padding
        min_v -= pixel_v_padding
        max_v += pixel_v_padding
        
        return (min_u, min_v, max_u, max_v)