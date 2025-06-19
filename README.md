# Blender2ARF Exporter

A Blender add-on that exports 3D avatars to the Avatar Representation Format (ARF) as specified in ISO/IEC 23090-39:2025. This exporter provides a comprehensive workflow for exporting avatars with meshes, skeletons, blendshapes, animations, and textures using an efficient external texture system.

## Current Features

### ✅ Core Export Capabilities
- **Multi-mesh avatars**: Export complete avatars with body, clothing, accessories, and props
- **Skeletal animation**: Full armature/skeleton export with bone hierarchies
- **Blendshapes**: Export shape keys for facial expressions and morphs (150+ shapes supported)
- **Animation clips**: Export skeletal animations from Blender actions
- **External texture system**: All textures exported as separate files for optimal reuse
- **Texture deduplication**: Automatic detection and sharing of identical textures
- **Asset-based organization**: Smart grouping of body parts vs. clothing/accessories
- **UV coordinate preservation**: Correctly handles texture atlases and UV mapping
- **Material support**: PBR materials with base color, metallic, and roughness

### ✅ ARF Compliance
- Generates fully compliant ARF containers (ZIP format)
- Creates proper ARF manifest (arf.json) with all required sections
- Supports OpenXR Face Tracking 2.0 blendshape mappings
- Supports OpenXR Body Tracking skeletal mappings
- Automatic ID generation and cross-referencing
- Interactive metadata collection (name, gender, age, height)
- Height-based automatic scaling for proper avatar proportions

### ✅ Technical Features
- **Blender to glTF conversion**: Proper coordinate system transformation
- **UV coordinate conversion**: Handles Blender to glTF UV system differences
- **Texture format support**: PNG, JPEG, WebP textures
- **Memory efficient**: External textures reduce GLB file sizes significantly
- **Progress bar**: Clean progress indication for non-debug mode
- **Smart scaling**: Automatic unit detection (mm, cm, m) and scaling
- **LOD support**: Optional level-of-detail generation (disabled by default)

## Architecture

The exporter uses a simplified, streamlined architecture:

```
arf_blender_export.py
    ├── Main export orchestration
    ├── ARF structure generation
    ├── Blender UI integration
    ├── Skeleton/armature export
    ├── Animation export
    ├── Blendshape organization
    ├── Metadata collection
    └── Height-based scaling
    
glb_exporter.py
    ├── Mesh to GLB conversion
    ├── Material processing
    ├── Blendshape export
    ├── Shape key handling
    └── Always uses external textures
    
external_texture_manager.py
    ├── Texture deduplication
    ├── Asset-based organization
    └── File management
    
uv_utils.py
    └── UV coordinate conversion
    
mesh_processor.py
    └── Mesh utilities
```

## Output Structure

The exporter creates a ZIP file with the following structure:

```
avatar.zip
├── arf.json              # ARF manifest
├── meshes/               # All mesh-related files
│   ├── Body.glb          # Mesh files with external texture references
│   ├── Clothing.glb
│   ├── Accessories.glb
│   └── textures/         # Shared texture directory
│       ├── character_skin_diffuse_abc123.jpg
│       ├── clothing_fabric_def456.png
│       └── metal_roughness_ghi789.jpg
├── blendshapes/          # Individual blendshape files
│   ├── Body_browInnerUp.glb
│   ├── Body_eyeBlinkLeft.glb
│   └── ...               # 150+ blendshape files
├── animations/           # Animation clips
│   ├── idle.glb
│   ├── walk.glb
│   └── ...
└── lods/                 # Level of detail meshes (optional)
    ├── Body_LOD1.glb
    ├── Body_LOD2.glb
    └── ...
```

### Texture Organization
- Textures are stored in `meshes/textures/`
- File names include asset prefix and content hash for deduplication
- GLB files reference textures using relative URIs: `textures/filename.ext`
- Identical textures are automatically shared between meshes

## Installation

### Method 1: Install as Blender Add-on (Recommended)
1. Download the `arf_blender_export.py` file
2. Open Blender and go to Edit → Preferences → Add-ons
3. Click "Install..." and select the downloaded file
4. Enable "Import-Export: ARF (Avatar Representation Format) Exporter"

### Method 2: Manual Installation
1. Clone or download this repository
2. Copy all `.py` files to your Blender scripts directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\[version]\scripts\addons\`
   - macOS: `/Users/[user]/Library/Application Support/Blender/[version]/scripts/addons/`
   - Linux: `~/.config/blender/[version]/scripts/addons/`

### Requirements
- Blender 2.80 or higher (tested with 4.0+)
- Python 3.7+ (included with Blender)
- NumPy (included with Blender)

## Usage

### GUI Export
1. Select the objects to export (meshes only in current version)
2. Go to File → Export → Avatar Representation Format (.zip)
3. Configure settings in the export panel
4. Click "Export ARF"

### Command Line Export
```bash
blender -b your_avatar.blend -P arf_blender_export.py -- --output avatar.zip
```

Basic Options:
- `--output PATH`: Output ZIP file path (required)
- `--scale FLOAT`: Scale factor (default: 1.0, auto-scales based on height if provided)
- `--debug`: Enable debug output
- `--no-animations`: Disable animation export
- `--no-blendshapes`: Disable blendshape export
- `--lods`: Enable LOD generation (disabled by default)

In headless mode, the exporter will prompt for metadata:
- Avatar name
- Gender (male/female/other/none)
- Age
- Height in meters (used for automatic scaling)

### Example Export Commands
```bash
# Basic export (will prompt for metadata)
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip

# Export with different scale
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --scale 0.01

# Export with debug output
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --debug

# Export without animations or blendshapes
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --no-animations --no-blendshapes

# Export with LOD generation
blender -b MyAvatar.blend -P arf_blender_export.py -- --output MyAvatar.zip --lods
```

## Export Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Scale | Export scale factor (auto-calculated from height if provided) | 1.0 |
| Export Animations | Export skeletal animations | True |
| Export Blendshapes | Export shape keys as blendshapes | True |
| Export Skeletons | Export armatures and bone hierarchies | True |
| Export Textures | Include material textures (always external) | True |
| Export LODs | Generate level-of-detail meshes | False |
| Debug Mode | Enable detailed logging | False |

## Code Structure

### Core Files
- **`arf_blender_export.py`** - Main Blender add-on
  - Handles Blender UI integration
  - Orchestrates the export process
  - Generates ARF manifest structure
  - Command-line argument parsing

- **`glb_exporter.py`** - Consolidated GLB exporter
  - Converts Blender meshes to glTF format
  - Always exports textures as external files
  - Handles material conversion
  - Performs coordinate system transformation

- **`external_texture_manager.py`** - Texture management system
  - Implements content-based deduplication
  - Organizes textures by asset
  - Generates proper relative URIs
  - Manages texture file I/O

- **`uv_utils.py`** - UV coordinate utilities
  - Converts between Blender and glTF UV systems
  - Handles texture atlas coordinates properly
  - Preserves UV mapping accuracy

- **`mesh_processor.py`** - Mesh processing utilities
  - Helper functions for mesh analysis
  - Mesh data extraction utilities

## Technical Details

### Coordinate System Conversion
- Blender uses Z-up, Y-forward coordinate system
- glTF uses Y-up, Z-forward coordinate system
- All positions, normals, and matrices are properly converted

### UV Coordinate Handling
- Blender UV origin is bottom-left (0,0)
- glTF UV origin is top-left (0,0)
- UV coordinates are flipped during export: `V_gltf = 1.0 - V_blender`
- Texture atlases are handled correctly with per-tile flipping

### Texture Management
- SHA256 hash-based deduplication
- Textures organized in `meshes/textures/` directory
- Relative URI references from GLB files
- Support for PNG, JPEG, and WebP formats

## Recent Updates

### Version 1.1.3 (Latest)
- ✅ Restored full blendshape export functionality (150+ shapes)
- ✅ Added clean progress bar for non-debug mode
- ✅ Interactive metadata prompts in headless mode
- ✅ Height-based automatic scaling with unit detection
- ✅ Fixed LOD export errors (disabled by default due to shape key conflicts)
- ✅ Reduced logging verbosity - use `--debug` for detailed output
- ✅ Ensured ARF compliance with required `supportedAnimations` field

### Features Restored
- Full skeletal animation export
- Complete blendshape/shape key support
- Skin weight export (tensor format)
- Animation clip export from Blender actions
- OpenXR mapping for face and body tracking

## Known Limitations

- **LOD with shape keys**: LOD generation may fail with meshes that have shape keys (disabled by default)
- **Texture atlases**: Complex UV layouts may need manual adjustment
- **Large textures**: Very large textures (>4K) may impact performance

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Priority areas for contribution:
- Re-implementing animation support
- Adding skeletal/skinning capabilities
- Performance optimization
- Documentation improvements

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Developed by Imed Bouazizi

Based on the ARF specification (ISO/IEC 23090-39:2025) developed by MPEG.

## Support

For issues and feature requests, please use the GitHub issue tracker.

For questions and discussions, use the GitHub Discussions tab.