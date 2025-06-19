# Blender2ARF Repository Information

## Repository Structure

```
blender2arf/
├── .gitignore              # Git ignore rules
├── LICENSE                 # MIT License
├── README.md              # Main documentation
├── README_blender.md      # Blender-specific details
├── CHANGELOG.md           # Version history
├── CONTRIBUTING.md        # Contribution guidelines
├── requirements.txt       # Python dependencies
├── arf_blender_export.py  # Main Blender add-on
└── blender_to_glb_simple.py # Custom GLB exporter
```

## Repository Setup Complete

The Blender2ARF exporter is now ready to be pushed to GitHub:

1. **Create a new repository on GitHub** named `blender2arf`
2. **Add the remote origin**:
   ```bash
   git remote add origin https://github.com/yourusername/blender2arf.git
   ```
3. **Push to GitHub**:
   ```bash
   git push -u origin main
   ```

## Key Features

- ✅ Complete ARF (ISO/IEC 23090-39:2025) compliance
- ✅ Tensor weight export enabled by default
- ✅ AnimationLinks for face tracking (50 mappings)
- ✅ AnimationLinks for body tracking (53 mappings)
- ✅ Multi-asset support with automatic organization
- ✅ LOD generation
- ✅ Blendshape export with basis shape
- ✅ Command-line and GUI export

## Recent Improvements

- Fixed tensor weight export to use default activation
- Fixed face tracking mappings to OpenXR standard
- Added body skeleton mappings to OpenXR Body Tracking
- Improved CC Base skeleton bone name detection
- Enhanced ARF compliance for all components

## Testing

The exporter has been tested with:
- CC Base avatars with full body rigging
- Multiple clothing items and accessories  
- 140+ blendshapes for facial expressions
- Tensor weight export for all skinned meshes

## Next Steps

1. Push to GitHub
2. Add CI/CD for automated testing
3. Create release packages for easy installation
4. Add more documentation and examples
5. Implement animation export support