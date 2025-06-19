# Blender2ARF Exporter

A Blender add-on that exports 3D avatars to the Avatar Representation Format (ARF) as specified in ISO/IEC 23090-39:2025. This exporter enables creators to export complex avatars with full support for meshes, skeletons, blendshapes, skin weights, and XR tracking mappings.

## Features

### Core Export Capabilities
- **Multi-mesh avatars**: Export complete avatars with body, clothing, accessories, and props
- **Skeletal animation**: Full armature/skeleton export with joint hierarchy
- **Blendshapes**: Export all shape keys as individual GLB files for facial expressions
- **Skin weights**: Efficient binary tensor format for vertex weights (float16 precision)
- **Level of Detail (LOD)**: Automatic generation of reduced-polygon versions

### ARF Compliance
- Generates fully compliant ARF containers (ZIP format)
- Creates proper ARF manifest (arf.json) with all required sections
- Organizes assets by type (meshes, blendshapes, data, lods)
- Automatic ID generation and cross-referencing
- Metadata support for avatar demographics

### XR Integration
- **Face Tracking**: Automatic mapping of blendshapes to OpenXR Face Tracking v2 standard
  - 50+ facial expression mappings
  - URN: `urn:khronos:openxr:facial-animation:fb-tracking2`
- **Body Tracking**: Automatic mapping of skeleton joints to OpenXR Body Tracking standard
  - 53 body joint mappings including fingers
  - URN: `urn:khronos:openxr:body-tracking:fb-body`

## Installation

### Method 1: Install as Blender Add-on (Recommended)
1. Download the `arf_blender_export.py` file
2. Open Blender and go to Edit → Preferences → Add-ons
3. Click "Install..." and select the downloaded file
4. Enable "Import-Export: ARF (Avatar Representation Format) Exporter"

### Method 2: Script Installation
1. Clone or download this repository
2. Copy the `blender2arf` folder to your Blender scripts directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\[version]\scripts\addons\`
   - macOS: `/Users/[user]/Library/Application Support/Blender/[version]/scripts/addons/`
   - Linux: `~/.config/blender/[version]/scripts/addons/`

### Requirements
- Blender 2.80 or higher
- Python 3.7+ (included with Blender)
- NumPy (included with Blender)

## Usage

### GUI Export
1. Select the objects to export (meshes and/or armatures)
2. Go to File → Export → Avatar Representation Format (.zip)
3. Configure settings in the export panel
4. Click "Export ARF"

### Command Line Export
```bash
blender -b your_avatar.blend -P arf_blender_export.py -- --output avatar.zip
```

Options:
- `--output PATH`: Output ZIP file path (required)
- `--scale FLOAT`: Scale factor (default: 1.0)
- `--no-animations`: Disable animation export
- `--no-blendshapes`: Disable blendshape export
- `--no-skeletons`: Disable skeleton export
- `--no-lods`: Disable LOD generation
- `--no-tensor-weights`: Use GLB format instead of tensor weights
- `--debug`: Enable debug output

### Example Export Command
```bash
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --scale 0.01 --debug
```

## Export Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Scale | Export scale factor | 1.0 |
| Export Animations | Include armature animations | True |
| Export Blendshapes | Export shape keys as blendshapes | True |
| Export Skeletons | Include armature/skeleton data | True |
| Export LODs | Generate level-of-detail meshes | True |
| Tensor Weights | Use binary format for skin weights | True |
| Tensor Precision | Float precision (16 or 32 bit) | 16 |
| Create Face Mapping | Auto-map to OpenXR face tracking | True |
| Create Body Mapping | Auto-map to OpenXR body tracking | True |
| Debug Mode | Enable detailed logging | False |

## Output Structure

The exporter creates a ZIP file containing:
```
avatar.zip
├── arf.json              # ARF manifest
├── meshes/               # Mesh geometry (GLB files)
│   ├── Body.glb
│   ├── Clothing.glb
│   └── Accessories.glb
├── blendshapes/          # Facial expressions (GLB files)
│   ├── Body_Smile.glb
│   ├── Body_Frown.glb
│   └── ...
├── data/                 # Binary data
│   ├── Body_skin_joints.bin
│   ├── Body_skin_weights.bin
│   └── ...
└── lods/                 # Level of detail meshes
    ├── Body_LOD2.glb
    └── Body_LOD3.glb
```

## Supported Avatar Types

- **Character Creator (CC) Base**: Full support with automatic XR mappings
- **Mixamo**: Skeleton and mesh export (manual mapping required)
- **Daz3D**: Export supported (manual mapping required)
- **Custom Rigs**: Any Blender armature with proper vertex groups

## TODO List

### High Priority
- [ ] **Animation Export**: Implement full animation clip export to GLB format
- [ ] **Material Export**: Properly export PBR materials and textures
- [ ] **Texture Optimization**: Implement UV bounds calculation and texture cropping
- [ ] **Validation**: Add pre-export validation and error reporting
- [ ] **Progress Bar**: Show export progress for large avatars

### Medium Priority
- [ ] **Hand Pose Presets**: Add common hand poses for XR applications
- [ ] **Compression Options**: Add Draco geometry compression support
- [ ] **Batch Export**: Support exporting multiple avatars at once
- [ ] **Export Presets**: Save and load export configurations
- [ ] **ARF Viewer**: Basic preview of exported ARF files

### Low Priority
- [ ] **Animation Retargeting**: Map animations between different skeleton types
- [ ] **Procedural LODs**: Smarter LOD generation with feature preservation
- [ ] **Texture Atlas**: Combine multiple textures into atlases
- [ ] **Morph Target Compression**: Optimize blendshape storage
- [ ] **Documentation**: Add video tutorials and example files

### Future Enhancements
- [ ] **MPEG-I Scene Description**: Support for scene composition
- [ ] **Streaming Format**: Progressive loading support
- [ ] **WebAssembly Version**: Browser-based export without Blender
- [ ] **Unity/Unreal Import**: Companion plugins for game engines
- [ ] **AI-Assisted Mapping**: Automatic detection of face/body landmarks

## Known Issues

1. **Animation Export**: Currently not implemented - animations are detected but not exported
2. **Large Blendshape Count**: Export may be slow with 100+ blendshapes
3. **Memory Usage**: Very high-poly meshes may require significant RAM
4. **Material Limitations**: Complex node-based materials may not export correctly

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Developed by Imed Bouazizi

Based on the ARF specification (ISO/IEC 23090-39:2025) developed by MPEG.

## Support

For issues and feature requests, please use the GitHub issue tracker.