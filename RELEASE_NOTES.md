# Release Notes

## 1.0.1 — Publication readiness

This release finalizes the public package surface for publication.

### Changes

- **SDK version**: `1.0.1`
- **MEP protocol version**: `2.0.0`
- removed placeholder project URLs from package metadata
- added GitHub Actions workflows for CI and trusted publishing
- added `MANIFEST.in` for cleaner source distributions
- removed bytecode caches from the release tree
- kept the protocol and runtime surfaces stable relative to `1.0.0`

### Recommended publication order

1. Push the repository to GitHub
2. Run CI on the default branch
3. Publish a test release to TestPyPI
4. Validate installation from TestPyPI
5. Tag `v1.0.1` and publish to PyPI
6. Create the GitHub Release from the tag
