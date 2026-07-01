# Screen Target Clicker

Windows desktop app that watches a selected window, finds target images with OpenCV template matching, and clicks matches automatically.

## Features

- Pick any visible window to scan
- Target images with configurable confidence
- Conditional click rules (primary + subsection must both match)
- Separate scan zones for targets and per-rule zones
- Live scan preview pinned to the target window
- Click cooldown, burst limits, and loop/wait tracking
- Global start/stop hotkey (default F6)
- Customizable dark UI with theme presets and fonts
- Portable build via PyInstaller

## Requirements

- Windows 10/11
- Python 3.11+ (3.14 tested)

## Run from source

```bat
py -m pip install -r requirements.txt
py main.py
```

Or double-click `run.bat`.

## Build portable exe

Close any running copy of the app, then:

```bat
build.bat
```

Output: `dist\ScreenTargetClicker\ScreenTargetClicker.exe`

Keep the entire `dist\ScreenTargetClicker\` folder together.

## Usage

1. **Window** — select the app to watch; optionally set a target scan zone
2. **Targets** — add images to click when matched
3. **Rules** — add paired rules (primary + subsection); optional per-rule scan zone
4. **Settings** — confidence, timing, hotkey, appearance
5. Press **START** or the hotkey to begin scanning

**Failsafe:** move the mouse to the top-left corner of the screen to abort PyAutoGUI actions.

## License

MIT
