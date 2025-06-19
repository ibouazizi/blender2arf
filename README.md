# Blender2ARF Exporter

A Blender add-on that exports 3D avatars to the Avatar Representation Format (ARF) as specified in ISO/IEC 23090-39:2025. This exporter enables creators to export complex avatars with full support for meshes, skeletons, blendshapes, skin weights, texture optimization, and XR tracking mappings.

## Current Status

### ✅ Implemented Features

#### Core Export Capabilities
- **Multi-mesh avatars**: Export complete avatars with body, clothing, accessories, and props
- **Skeletal animation**: Full armature/skeleton export with joint hierarchy
- **Blendshapes**: Export all shape keys as individual GLB files for facial expressions
- **Skin weights**: Efficient binary tensor format for vertex weights (float16/32 precision)
- **Level of Detail (LOD)**: Automatic generation of reduced-polygon versions
- **Texture Export**: Full support for PBR materials and textures in GLB format
- **Texture Cropping**: Automatic optimization of textures based on UV usage
  - Crops unused texture regions
  - Power-of-2 dimension alignment
  - UV coordinate remapping
  - Configurable area threshold (90%)

#### ARF Compliance
- Generates fully compliant ARF containers (ZIP format)
- Creates proper ARF manifest (arf.json) with all required sections
- Organizes assets by type (meshes, blendshapes, data, lods)
- Automatic ID generation and cross-referencing
- Metadata support for avatar demographics

#### XR Integration
- **Face Tracking**: Automatic mapping of blendshapes to OpenXR Face Tracking v2 standard
  - 50+ facial expression mappings
  - URN: `urn:khronos:openxr:facial-animation:fb-tracking2`
- **Body Tracking**: Automatic mapping of skeleton joints to OpenXR Body Tracking standard
  - 53 body joint mappings including fingers
  - URN: `urn:khronos:openxr:body-tracking:fb-body`

### ⚠️ Limitations
- Animation clips export not yet implemented (detected but not exported)
- Complex node-based materials may simplify during export
- Very large textures (>4K) may require significant memory

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
- Blender 2.80 or higher (tested with 4.0+)
- Python 3.7+ (included with Blender)
- NumPy (included with Blender)

### Optional Dependencies
- PIL/Pillow: Required for texture cropping functionality
  - Install via: `pip install Pillow` or use provided `install_pil.py` script

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
- `--no-textures`: Disable texture export
- `--no-lods`: Disable LOD generation
- `--no-tensor-weights`: Use GLB format instead of tensor weights
- `--crop-textures`: Enable texture cropping optimization
- `--debug`: Enable debug output

### Example Export Commands
```bash
# Basic export
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip

# Export with texture optimization
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --crop-textures --debug

# Export at different scale
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --scale 0.01
```

## Export Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Scale | Export scale factor | 1.0 |
| Export Animations | Include armature animations | True |
| Export Blendshapes | Export shape keys as blendshapes | True |
| Export Skeletons | Include armature/skeleton data | True |
| Export Textures | Include material textures | True |
| Export LODs | Generate level-of-detail meshes | True |
| Crop Textures | Optimize textures by cropping unused areas | False |
| LOD Count | Number of LOD levels to generate | 3 |
| LOD Ratio | Decimation ratio between LOD levels | 0.5 |
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
├── meshes/               # Mesh geometry (GLB files with materials)
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

## TODO List

### 🎯 High Priority - Core Functionality

#### GUI Enhancements
- [ ] **Export Options Panel**: Enhance Blender UI panel with all export options
  - [ ] Collapsible sections for different option groups
  - [ ] Real-time validation feedback
  - [ ] Export preset management (save/load configurations)
  - [ ] Progress bar with cancel option

#### Animation Mapping Editor
- [ ] **AnimationLinks Editor**: GUI for customizing animation mappings
  - [ ] Visual joint mapping interface
  - [ ] Load/save custom mapping profiles
  - [ ] Preview mapped animations
  - [ ] Support for retargeting between different skeleton types
  - [ ] Batch mapping operations

#### User Metadata Interface
- [ ] **Metadata Editor Panel**: Form-based UI for avatar metadata
  - [ ] Avatar information (name, author, version, license)
  - [ ] Demographics data entry
  - [ ] Custom metadata fields
  - [ ] Validation against ARF schema
  - [ ] Import/export metadata templates

### 🔧 Medium Priority - Enhanced Features

#### Export Functionality
- [ ] **Animation Clip Export**: Full implementation of animation export
  - [ ] Support for multiple animation clips
  - [ ] Animation trimming and looping options
  - [ ] Keyframe optimization
  - [ ] Root motion extraction options

#### Material System
- [ ] **Advanced Material Export**: Better material conversion
  - [ ] Support for complex shader nodes
  - [ ] Normal map tangent space handling
  - [ ] Emission and clearcoat support
  - [ ] Material preset library

#### Validation & Preview
- [ ] **Pre-Export Validation**: Comprehensive checks before export
  - [ ] Mesh validation (manifold, UV coverage)
  - [ ] Texture size warnings
  - [ ] Bone count limits
  - [ ] Naming convention checks
  
- [ ] **ARF Preview Window**: Built-in viewer for exported files
  - [ ] 3D preview with materials
  - [ ] Animation playback
  - [ ] Blendshape testing
  - [ ] File size analysis

### 📊 Low Priority - Advanced Features

#### Optimization Tools
- [ ] **Texture Atlas Generator**: Combine multiple textures
  - [ ] Automatic UV repacking
  - [ ] Channel packing options
  - [ ] Resolution optimization
  
- [ ] **Mesh Optimization**: Advanced geometry processing
  - [ ] Automatic decimation with feature preservation
  - [ ] Vertex cache optimization
  - [ ] Duplicate vertex welding

#### Workflow Features
- [ ] **Batch Processing**: Multiple avatar export
  - [ ] Folder watch mode
  - [ ] Command-line batch interface
  - [ ] Export queue management
  
- [ ] **Version Control Integration**: Git-friendly exports
  - [ ] Incremental export detection
  - [ ] Diff visualization for ARF files
  - [ ] Change log generation

### 🚀 Future Enhancements

#### Platform Integration
- [ ] **Web-Based Exporter**: Browser version using Blender Cloud
- [ ] **Game Engine Plugins**: Direct export to Unity/Unreal
- [ ] **Cloud Processing**: Server-based optimization pipeline
- [ ] **Mobile Preview**: AR preview on mobile devices

#### AI-Powered Features
- [ ] **Auto-Rigging**: Automatic skeleton detection and weighting
- [ ] **Smart LOD Generation**: AI-based detail preservation
- [ ] **Expression Transfer**: Map expressions between different topologies
- [ ] **Texture Enhancement**: AI upscaling and optimization

#### Standards Support
- [ ] **USD Export**: Universal Scene Description format
- [ ] **VRM Support**: VRM avatar format compatibility
- [ ] **GLTF Extensions**: Support for latest glTF extensions
- [ ] **OpenXR Extensions**: New tracking standards as released

## Architecture

The exporter is organized into modular components:

- `arf_blender_export.py` - Main Blender add-on and export orchestration
- `glb_exporter.py` - Core GLB/glTF export functionality
- `glb_exporter_cropped.py` - Extended GLB exporter with texture cropping
- `texture_cropper.py` - Texture optimization and UV remapping utilities
- `mesh_processor.py` - Mesh analysis and processing utilities

## Known Issues

1. **Memory Usage**: Very high-poly meshes (>1M vertices) may require significant RAM
2. **Shader Nodes**: Some complex Blender shader setups may not translate perfectly
3. **Animation Baking**: IK and constraint-based animations need manual baking before export

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Priority areas for contribution:
- Animation export implementation
- GUI enhancement (especially the metadata and mapping editors)
- Additional file format support
- Performance optimization
- Documentation and tutorials

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Developed by Imed Bouazizi

Based on the ARF specification (ISO/IEC 23090-39:2025) developed by MPEG.

Special thanks to the Blender community and glTF working group.

## Support

For issues and feature requests, please use the GitHub issue tracker.

For questions and discussions, use the GitHub Discussions tab.