# GitHub Publication Guide

## 1. Create the repository

Create a public repository, for example `AxiomMesh-SDK`.

## 2. Update package metadata

Before publishing, set the real repository URLs in `pyproject.toml` under `[project.urls]` if you want them exposed on PyPI.

## 3. Push the code

```bash
git init
git branch -M main
git add .
git commit -m "Release AxiomMesh SDK 1.0.1"
git remote add origin git@github.com:YOUR-ACCOUNT/AxiomMesh-SDK.git
git push -u origin main
```

## 4. Configure GitHub Actions

The repository already contains:

- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`

CI will run on pushes and pull requests. Publishing runs when you push a tag like `v1.0.1`.

## 5. Configure PyPI Trusted Publishing

On PyPI, add the GitHub repository as a Trusted Publisher for the package. Then the publish workflow can upload without a long-lived API token.

## 6. Tag a release

```bash
git tag v1.0.1
git push origin v1.0.1
```

## 7. Create the GitHub Release

On GitHub:

- open **Releases**
- click **Draft a new release**
- choose tag `v1.0.1`
- title it `AxiomMesh SDK v1.0.1`
- paste notes from `RELEASE_NOTES.md`

## 8. Recommended order

1. push to GitHub
2. confirm CI passes
3. publish to TestPyPI manually or with a test workflow
4. validate install
5. push the final tag
6. create the GitHub Release
