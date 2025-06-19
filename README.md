# Blender2ARF Exporter

A Blender add-on for exporting 3D avatars to the Avatar Representation Format (ARF) as specified in ISO/IEC 23090-39:2025.

## Features

- **Complete ARF Compliance**: Exports avatars in full compliance with the ARF specification
- **Multi-Asset Support**: Handles complex avatars with multiple meshes, clothing, and accessories
- **Tensor Weight Export**: Efficient storage of skin weights using binary tensor format
- **LOD Generation**: Automatic Level-of-Detail creation for optimized rendering
- **Blendshape Export**: Full support for facial expressions and morph targets
- **Animation Support**: Export skeleton-based animations (in development)
- **XR Mapping**: Automatic mapping to OpenXR standards for face and body tracking
- **Metadata Support**: Comprehensive avatar metadata including demographics and biometrics

## Installation

1. Download the `blender2arf` folder
2. In Blender, go to Edit → Preferences → Add-ons
3. Click "Install..." and select the `arf_blender_export.py` file
4. Enable the "Avatar Representation Format (ARF) Exporter" add-on

## Usage

### GUI Export

1. Select the objects you want to export (meshes and/or armatures)
2. Go to File → Export → Avatar Representation Format (.zip)
3. Configure export settings:
   - **Scale**: Export scale factor (default: 1.0)
   - **Export Animations**: Include animations from armatures
   - **Export Blendshapes**: Include shape keys as blendshapes
   - **Export Skeletons**: Include armature data
   - **Export LODs**: Generate Level-of-Detail meshes
   - **Tensor Weights**: Use efficient binary format for skin weights
   - **Create Face/Body Mapping**: Auto-generate XR tracking mappings
4. Click "Export ARF"

### Command Line Export

```bash
blender -b your_file.blend -P path/to/arf_blender_export.py -- --output output.zip [options]
```

Options:
- `--output`: Output ZIP file path (required)
- `--scale`: Export scale factor (default: 1.0)
- `--no-animations`: Disable animation export
- `--no-blendshapes`: Disable blendshape export
- `--no-skeletons`: Disable skeleton export
- `--no-lods`: Disable LOD generation
- `--no-tensor-weights`: Use GLB format for weights instead of tensors
- `--debug`: Enable debug output

## ARF Structure

The exporter creates a ZIP container with the following structure:

```
output.zip
├── arf.json          # ARF manifest file
├── meshes/           # Mesh geometry files (GLB format)
├── blendshapes/      # Blendshape files (GLB format)
├── data/             # Binary tensor data for skin weights
├── lods/             # Level-of-detail meshes
└── animations/       # Animation files (when implemented)
```

## AnimationLinks

The exporter automatically creates AnimationLinks for:

### Face Tracking
- Maps CC Base blendshapes to OpenXR Face Tracking v2 (XR_FB_face_tracking2)
- Supports 50+ facial expressions
- URN: `urn:khronos:openxr:facial-animation:fb-tracking2`

### Body Tracking
- Maps CC Base skeleton to OpenXR Body Tracking (XR_FB_body_tracking)
- Supports full body including fingers
- URN: `urn:khronos:openxr:body-tracking:fb-body`

## Requirements

- Blender 2.80 or higher
- Python 3.7+
- NumPy (for tensor weight export)

## Development

### File Structure
- `arf_blender_export.py`: Main exporter add-on
- `blender_to_glb_simple.py`: Custom GLB exporter for mesh data
- `README_blender.md`: Blender-specific documentation

### Key Classes
- `ExportARF`: Main export operator
- `ARFExportSettings`: Export configuration properties
- `organize_by_asset_type()`: Core export logic
- `create_face_animation_link()`: Face tracking mapping
- `create_body_animation_link()`: Body tracking mapping

## Limitations

- Animation export is currently in development
- Texture cropping for optimized UV bounds is not yet implemented
- Some advanced ARF features may require manual editing of the output

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Credits

Developed by Imed Bouazizi as part of the ARF (Avatar Representation Format) implementation.