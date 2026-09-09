# Meme Picker for Linux

Meme Picker is a searchable Linux system tray application for browsing and copying reaction images, GIFs, and memes. It uses **PyQt6**, supports native Wayland clipboard copying through `wl-copy`, and can keep a selected local folder synchronized with an iCloud `rclone` remote.

This is an independent, unofficial project and is not affiliated with, endorsed by, or sponsored by Apple or any other trademark owner.

## Features

- Multi-word search with accent and Turkish-character normalization.
- Grid and list views with thumbnail loading and adjustable zoom.
- Native Wayland clipboard copying, with the Qt clipboard as a fallback.
- Optional bidirectional synchronization through `rclone bisync`.
- Interactive iCloud session reconnection through an available terminal emulator.
- System tray support.
- User-selectable meme folder. The default is the platform's Pictures directory followed by `memes` (normally `~/Pictures/memes`).

## Scope and limitations

Meme Picker manages image files in one local folder and optionally synchronizes that folder with `icloud:memes`. It does not provide its own cloud storage, account management, encryption, or conflict history. The application assumes that `rclone` is already configured when synchronization is enabled.

## Requirements

| Component | Purpose |
| --- | --- |
| Python 3 | Runs the application |
| PyQt6 | Desktop user interface |
| `wl-copy` from `wl-clipboard` | Optional native Wayland image clipboard support |
| `rclone` | Optional iCloud synchronization and session reconnection |
| A supported terminal emulator | Optional 2FA reconnection (`konsole`, `kitty`, `alacritty`, `foot`, or `xterm`) |
| Dolphin or another file manager | Optional “Show in File Manager” integration |

The application is primarily intended for Linux desktop environments. It is started as a regular Python process and remains available from the system tray; installing a desktop application launcher is optional. Closing or hiding the window does not exit the application. Wayland is recommended for native clipboard integration; Qt may still provide clipboard support on other display systems, including X11.

On Arch Linux or CachyOS:

```bash
paru -S python-pyqt6 wl-clipboard rclone
```

Install the equivalent packages for other distributions. No Python package installation is required beyond the distribution's PyQt6 package.

## Installation and usage

Clone or download the repository, then run:

```bash
python3 meme-picker.py
```

On first launch, the default meme folder is created automatically. Use the folder button or the tray menu's **Choose Meme Folder** action to select another directory. The selected path is stored in the desktop settings and remains active on later launches.

Supported image extensions are `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.heic`, and `.heif`.
HEIC and HEIF files are decoded by Qt when the installed PyQt6 image plugins provide support.
When an image is copied, it is encoded as PNG for clipboard compatibility.
Meme Picker reads thumbnails and images from the selected local folder, so existing files remain available offline. Synchronization with iCloud is a separate background operation.

## iCloud synchronization

Meme Picker uses `rclone bisync` so the same `memes` collection can be edited from both a phone and a PC through iCloud. The local folder is synchronized with `icloud:memes` in both directions.

1. Configure an iCloud remote:

   ```bash
   rclone config
   ```

2. Name the remote `icloud`.
3. Ensure that the remote folder `icloud:memes` exists.
4. Select the local folder to synchronize in Meme Picker.

The application starts a sync at launch and when the sync button is pressed. It uses `--conflict-resolve newer`, `--resilient`, and `--create-empty-src-dirs`. If the regular bisync operation fails, it retries with `--resync`.

Before the first synchronization or resync, make a backup of important files and confirm that the selected local folder is dedicated to this meme collection. `rclone bisync` may download, upload, rename, or delete files in either location according to its state and conflict policy. Review the resulting `rclone` output before accepting unexpected changes.

The iCloud remote's credentials are managed by `rclone`; Meme Picker does not store or display them. Use **Reconnect Session** when `rclone` requires a fresh 2FA session.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| Meme folder | Platform Pictures directory + `memes` | Local image directory; selectable from the application |
| Remote | `icloud:memes` | Remote folder used by `rclone bisync` |
| Conflict policy | Newer file wins | Passed to `rclone` as `--conflict-resolve newer` |
| View mode | Grid | Can be changed to list view |
| Zoom | 130 | Stored per desktop user through Qt settings |

## Optional desktop launcher

The desktop entry is optional. The application does not require a desktop launcher and can be started directly from a terminal while remaining in the system tray. If you want a menu entry, the included desktop entry uses `/path/to/project` as a portable placeholder. Replace it with the absolute repository path during installation:

```bash
PROJECT_DIR="$PWD"
mkdir -p ~/.local/share/applications
sed "s|/path/to/project|$PROJECT_DIR|g" \
  meme-picker.desktop > ~/.local/share/applications/meme-picker.desktop
```

If the repository is moved later, reinstall the desktop entry with the new path.

KDE Autostart is a separate optional configuration. It is not required for normal use and is not installed by this repository.

## Troubleshooting

- **`rclone missing`:** Install `rclone` and ensure it is available on `PATH`.
- **Sync errors:** Run `rclone bisync icloud:memes /path/to/project/memes --verbose` manually and check the remote configuration.
- **Clipboard does not paste on Wayland:** Install `wl-clipboard` and verify that `wl-copy` works in the current session.
- **2FA reconnect does not open:** Install one of the supported terminal emulators or reconnect with `rclone config reconnect icloud:`.
- **No images appear:** Confirm that the selected folder contains a supported image extension.
- **HEIC or HEIF does not open:** Confirm that the installed PyQt6/Qt image plugins include HEIC/HEIF support.

## Manual test checklist

The following checks require a Linux desktop session and are not run in CI:

- Start `python3 meme-picker.py` and confirm that the application remains available from the system tray.
- Confirm that the local meme folder can be browsed while offline.
- Search using multiple words and Turkish characters or accents.
- Open a HEIC/HEIF thumbnail and copy it; confirm that the clipboard receives a PNG image.
- On Wayland, verify `wl-copy` clipboard integration.
- Run a controlled `rclone bisync` test and review its output before using a real collection.
- Confirm that the optional folder and desktop integrations open the expected applications.

## Security and privacy

The application reads and writes only the selected meme folder and Qt's local settings. `rclone` may read, upload, download, rename, or delete files as required by bidirectional synchronization. Do not select a folder containing unrelated personal data. Review `rclone` configuration permissions and keep credentials out of the repository.

## Uninstall

Remove the installed desktop entry and the repository:

```bash
rm ~/.local/share/applications/meme-picker.desktop
rm -rf /path/to/project
```

The selected meme folder and `rclone` configuration are not removed automatically. Delete them separately only if they are no longer needed.

## Third-party components

Meme Picker uses PyQt6, `wl-clipboard`, and `rclone` as external components. Their own licenses and terms apply. The repository's icon is a simple local SVG asset.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
