# Contributing to Blender2ARF

Thank you for your interest in contributing to the Blender2ARF exporter! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/blender2arf.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes thoroughly
6. Commit your changes: `git commit -m "Add your feature"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Create a pull request

## Development Setup

1. Install Blender 2.80 or higher
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Link or copy the blender2arf folder to your Blender addons directory

## Code Style

- Follow PEP 8 Python style guidelines
- Use descriptive variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and modular
- Comment complex logic

## Testing

Before submitting a pull request:

1. Test with various avatar types:
   - Single mesh avatars
   - Multi-mesh avatars with clothing
   - Avatars with blendshapes
   - Rigged characters with animations

2. Verify ARF compliance:
   - Run the exported files through ARF validators
   - Check that all components are properly referenced
   - Ensure tensor weights export correctly

3. Test both GUI and command-line export

## Reporting Issues

When reporting issues, please include:

1. Blender version
2. Operating system
3. Steps to reproduce the issue
4. Error messages (if any)
5. Sample .blend file (if possible)

## Feature Requests

We welcome feature requests! Please:

1. Check existing issues to avoid duplicates
2. Clearly describe the feature and its use case
3. Explain how it would benefit ARF export workflow

## Pull Request Guidelines

- Keep pull requests focused on a single feature or fix
- Update documentation if needed
- Add entries to CHANGELOG.md
- Ensure all tests pass
- Follow the existing code structure

## Areas for Contribution

Current areas where contributions are especially welcome:

1. **Animation Export**: Implementing full animation export support
2. **Texture Optimization**: UV bounds calculation and texture cropping
3. **Performance**: Optimizing export for large avatars
4. **Standards Compliance**: Ensuring full ARF specification compliance
5. **Documentation**: Improving user guides and examples
6. **Testing**: Adding automated tests

## License

By contributing to Blender2ARF, you agree that your contributions will be licensed under the MIT License.