# Screen Target Clicker

Windows app that watches a selected window, finds target images, and clicks matches automatically.

**Download:** [GitHub Releases](https://github.com/natchotacochimichanga-commits/screen-target-clicker/releases/latest)  
**Website:** [natchotacochimichanga-commits.github.io/screen-target-clicker](https://natchotacochimichanga-commits.github.io/screen-target-clicker/)

## Requirements

- Windows 10/11
- Python 3.11+ to build the portable exe

## Build portable release

```bat
build.bat
package-portable.bat
release.bat v1.2
```

The repo contains **obfuscated** app code. Readable source lives in `src/` on your machine only (gitignored).

## Local development

Edit files in `src/`, then run:

```bat
run.bat
```

Before pushing to GitHub:

```bat
sync-github.bat
```

That obfuscates `src/` into the repo root and removes non-app clutter.

## License

MIT
