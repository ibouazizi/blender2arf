# Changelog

All notable changes to the Blender2ARF Exporter will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.3] - 2025-01-19

### Added
- Body skeleton mappings to OpenXR Body Tracking standard
- Support for 53 body joint mappings including fingers
- Automatic detection and mapping of CC Base skeleton bones

### Fixed
- Tensor weights now export by default without requiring flags
- Tensor data now stored in "data" folder instead of "tensors"
- Face tracking mappings now correctly identify blendshapes
- AnimationLinks properly reference URNs for OpenXR standards

### Changed
- Improved bone name matching for CC Base skeletons
- Enhanced debug output for AnimationLink creation

## [1.1.2] - 2025-01-18

### Added
- AnimationLinks support for face tracking mappings
- OpenXR Face Tracking v2 (XR_FB_face_tracking2) support
- 50 facial expression mappings for CC Base avatars

## [1.1.1] - 2025-01-17

### Added
- Tensor weight export for efficient skin weight storage
- Binary format (.bin) for joint indices and weights
- Float16 precision support for reduced file size

## [1.1.0] - 2025-01-15

### Added
- Multi-asset export with automatic organization
- Support for complex avatars with clothing and accessories
- LOD (Level of Detail) generation
- Blendshape export with basis shape

### Fixed
- Proper ARF compliance for all exported components
- Correct ID generation for all elements

## [1.0.0] - 2025-01-10

### Added
- Initial release of Blender2ARF Exporter
- Basic mesh export to GLB format
- Skeleton export with armature support
- ARF manifest generation
- Command line and GUI export options