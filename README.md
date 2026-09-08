# Meme Picker for Linux

A fast, searchable desktop picker for reaction images, GIFs, and memes built with **PyQt6**, featuring **native Wayland clipboard copying (`wl-copy`)**, **asynchronous thumbnail caching**, and optional **iCloud bi-directional synchronization via `rclone`**.

---

## ✨ Features

- **Blazing Fast Search:** Multi-word instant filtering with full diacritics / accent normalization.
- **Native Wayland Clipboard Integration:** Directly copies image byte data to the clipboard using `wl-copy`, allowing seamless instant pasting (`Ctrl+V`) into Discord, Telegram, Slack, and web browsers.
- **Bi-Directional Cloud Sync:** Synchronizes your meme folder with cloud storage (configured by default for iCloud via `rclone bisync`).
- **Interactive 2FA Reconnection:** Automatically detects and opens your preferred terminal emulator to handle 2FA Apple ID authentication refreshes.
- **Smooth Adaptive Grid:** Dynamically adjusts image cards based on window size with interactive zoom scaling.
- **System Tray & Quick Access:** Minimizes to the system tray for zero-friction background availability.

---

## 📦 Requirements

On Arch Linux / CachyOS:
```bash
paru -S python-pyqt6 wl-clipboard rclone
```

---

## 🚀 Setup & Usage

### 1. Meme Storage Directory
The application automatically monitors and populates:
```bash
~/Pictures/memes   # (or ~/Resimler/memes on Turkish systems)
```
Simply drop your `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp` files here!

### 2. (Optional) iCloud Synchronization Setup
To enable automatic bi-directional syncing with your iCloud Drive:
1. Configure an iCloud remote in `rclone`:
```bash
rclone config
```
*(Name the remote `icloud`).*
2. Ensure you have a folder named `memes` in your iCloud Drive root (`icloud:memes`).

---

## ⌨️ Desktop Launcher
To add Meme Picker to your application menu (KDE Kickoff, Rofi, GNOME):
```bash
mkdir -p ~/.local/share/applications
cp meme-picker.desktop ~/.local/share/applications/
```

---

## 📜 License
MIT License
