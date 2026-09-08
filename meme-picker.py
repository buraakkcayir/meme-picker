#!/usr/bin/env python3
import sys
import os
import shutil
import subprocess
import unicodedata
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QSystemTrayIcon, QMenu, QLabel, QSlider, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QBuffer, QIODevice, QUrl, QSettings
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QImageReader, QDesktopServices
)

# Dynamic Pictures Directory (Supports English and Turkish locales)
HOME = Path.home()
PICTURES_DIR = HOME / "Pictures"
if not PICTURES_DIR.exists() and (HOME / "Resimler").exists():
    PICTURES_DIR = HOME / "Resimler"

LOCAL_MEME_DIR = PICTURES_DIR / "memes"
OLD_MEME_DIR = HOME / "Memes"

if OLD_MEME_DIR.exists() and not LOCAL_MEME_DIR.exists():
    LOCAL_MEME_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(OLD_MEME_DIR), str(LOCAL_MEME_DIR))

LOCAL_MEME_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ICON_PATH = HOME / ".local" / "share" / "icons" / "meme-picker.svg"

SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <circle cx="64" cy="64" r="48" fill="none" stroke="#eff0f1" stroke-width="8" stroke-linecap="round"/>
  <ellipse cx="46" cy="48" rx="5.5" ry="7.5" fill="#eff0f1"/>
  <ellipse cx="82" cy="48" rx="5.5" ry="7.5" fill="#eff0f1"/>
  <path d="M 40 74 L 88 74 C 88 98 40 98 40 74 Z" fill="none" stroke="#eff0f1" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

def get_app_icon() -> QIcon:
    if not ICON_PATH.exists():
        ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        ICON_PATH.write_text(SVG_CONTENT)
    return QIcon(str(ICON_PATH))

def normalize_text(text: str) -> str:
    tr_map = str.maketrans({
        "İ": "i", "I": "i", "ı": "i",
        "Ş": "s", "ş": "s",
        "Ğ": "g", "ğ": "g",
        "Ü": "u", "ü": "u",
        "Ö": "o", "ö": "o",
        "Ç": "c", "ç": "c"
    })
    cleaned = text.translate(tr_map).lower()
    # Normalize unicode accents
    return "".join(c for c in unicodedata.normalize("NFD", cleaned) if unicodedata.category(c) != "Mn")

def format_to_3_lines(text: str, chars_per_line: int = 18) -> str:
    words = text.strip().split()
    if not words:
        return ""

    lines = []
    cur_line = []
    cur_len = 0

    for w in words:
        w_len = len(w)
        add_len = w_len + (1 if cur_line else 0)

        if cur_len + add_len <= chars_per_line:
            cur_line.append(w)
            cur_len += add_len
        else:
            if cur_line:
                lines.append(" ".join(cur_line))
            else:
                lines.append(w[:chars_per_line])
                w = w[chars_per_line:]
            cur_line = [w] if w else []
            cur_len = len(w)

            if len(lines) == 3:
                break

    if cur_line and len(lines) < 3:
        lines.append(" ".join(cur_line))

    used_words = sum(len(l.split()) for l in lines)
    if used_words < len(words) or len(lines) > 3:
        lines = lines[:3]
        if lines:
            lines[-1] = lines[-1].rstrip(". ") + "..."

    return "\n".join(lines[:3])

class BiSyncWorker(QThread):
    sync_finished = pyqtSignal(bool, str)

    def run(self):
        if not shutil.which("rclone"):
            self.sync_finished.emit(False, "rclone missing")
            return

        try:
            cmd = [
                "rclone", "bisync",
                "icloud:memes", str(LOCAL_MEME_DIR),
                "--resilient",
                "--conflict-resolve", "newer",
                "--create-empty-src-dirs"
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)

            if proc.returncode != 0:
                cmd_resync = cmd + ["--resync"]
                proc = subprocess.run(cmd_resync, capture_output=True, text=True)

            if proc.returncode == 0:
                self.sync_finished.emit(True, "Synced")
            else:
                err_snippet = proc.stderr.strip().splitlines()[-1] if proc.stderr else "Sync Error"
                self.sync_finished.emit(False, err_snippet[:30])
        except Exception as e:
            self.sync_finished.emit(False, str(e)[:30])

class ProcessWatcher(QThread):
    watcher_done = pyqtSignal()

    def __init__(self, proc):
        super().__init__()
        self.proc = proc

    def run(self):
        self.proc.wait()
        self.watcher_done.emit()

class ThumbnailLoader(QThread):
    thumb_ready = pyqtSignal(str, QPixmap)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths
        self.is_running = True

    def run(self):
        for path in self.paths:
            if not self.is_running:
                break
            reader = QImageReader(str(path))
            reader.setScaledSize(QSize(240, 210))
            img = reader.read()
            if not img.isNull():
                pix = QPixmap.fromImage(img)
                self.thumb_ready.emit(str(path), pix)

    def stop(self):
        self.is_running = False

class MemePicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meme Picker")
        self.settings = QSettings("MemePicker", "MemeFinder")

        self.item_map = {}
        self.thumb_worker = None
        self.sync_worker = None
        self.auth_watcher = None
        self.last_sync_time = ""
        self.last_sync_msg = "Syncing..."

        self.view_mode = self.settings.value("view_mode", "grid")

        app_icon = get_app_icon()
        self.setWindowIcon(app_icon)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Top Bar
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search memes...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 14px;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.05);
                color: #ffffff;
            }
            QLineEdit:focus { border: 1px solid #3daee9; }
        """)
        self.search_bar.textChanged.connect(self.filter_memes)
        top_layout.addWidget(self.search_bar, stretch=1)

        self.auth_btn = QPushButton()
        key_icon = QIcon.fromTheme("dialog-password")
        if not key_icon.isNull():
            self.auth_btn.setIcon(key_icon)
        else:
            self.auth_btn.setText("🔑")
        self.auth_btn.setToolTip("Reconnect iCloud Session (2FA Auth)")
        self.auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auth_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.08);
                border: none;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.16); }
        """)
        self.auth_btn.clicked.connect(self.reconnect_session)
        top_layout.addWidget(self.auth_btn)

        self.folder_btn = QPushButton()
        folder_icon = QIcon.fromTheme("folder-open")
        if not folder_icon.isNull():
            self.folder_btn.setIcon(folder_icon)
        else:
            self.folder_btn.setText("📁")
        self.folder_btn.setToolTip("Open Local Folder")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.08);
                border: none;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.16); }
        """)
        self.folder_btn.clicked.connect(self.open_meme_folder)
        top_layout.addWidget(self.folder_btn)

        self.refresh_btn = QPushButton()
        refresh_icon = QIcon.fromTheme("view-refresh")
        if not refresh_icon.isNull():
            self.refresh_btn.setIcon(refresh_icon)
        else:
            self.refresh_btn.setText("🔄")
        self.refresh_btn.setToolTip("Sync Cloud")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.08);
                border: none;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.16); }
        """)
        self.refresh_btn.clicked.connect(self.start_sync)
        top_layout.addWidget(self.refresh_btn)

        layout.addLayout(top_layout)

        # List / Grid Area
        self.list_widget = QListWidget()
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.verticalScrollBar().setSingleStep(25)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QCornerWidget {
                background: transparent;
            }
            QListWidget::item {
                background: rgba(255, 255, 255, 0.04);
                border-radius: 10px;
                padding: 6px;
                margin: 4px;
                border: 1px solid rgba(255, 255, 255, 0.03);
                color: #eff0f1;
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.09);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
            QListWidget::item:selected {
                background: rgba(61, 174, 233, 0.22);
                border: 1px solid #3daee9;
                color: #ffffff;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.copy_and_hide)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.list_widget)

        # Bottom Bar (Status + View Toggle + Zoom Slider)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(2, 0, 2, 0)
        bottom_layout.setSpacing(6)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        bottom_layout.addWidget(self.status_label, stretch=1)

        self.view_btn = QPushButton()
        self.view_btn.setFixedSize(26, 22)
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
                color: #eff0f1;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.16); }
        """)
        self.view_btn.clicked.connect(self.toggle_view_mode)
        bottom_layout.addWidget(self.view_btn)

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedSize(22, 22)
        self.zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
                color: #eff0f1;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.16); }
        """)
        self.zoom_out_btn.clicked.connect(lambda: self.zoom_slider.setValue(self.zoom_slider.value() - 15))
        bottom_layout.addWidget(self.zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(90, 210)
        self.zoom_slider.setFixedWidth(85)
        self.zoom_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        bottom_layout.addWidget(self.zoom_slider)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(22, 22)
        self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
                color: #eff0f1;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.16); }
        """)
        self.zoom_in_btn.clicked.connect(lambda: self.zoom_slider.setValue(self.zoom_slider.value() + 15))
        bottom_layout.addWidget(self.zoom_in_btn)

        layout.addLayout(bottom_layout)

        # System Tray
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(app_icon)
        self.tray.setToolTip("Meme Picker")

        menu = QMenu()
        sync_action = menu.addAction("🔄 Sync Now")
        sync_action.triggered.connect(self.start_sync)
        auth_action = menu.addAction("🔑 Reconnect Session")
        auth_action.triggered.connect(self.reconnect_session)
        open_action = menu.addAction("📁 Open Folder")
        open_action.triggered.connect(self.open_meme_folder)
        exit_action = menu.addAction("❌ Quit")
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_click)
        self.tray.show()

        saved_zoom = self.settings.value("zoom", 130, type=int)
        self.zoom_slider.setValue(saved_zoom)

        saved_geo = self.settings.value("geometry")
        if saved_geo:
            self.restoreGeometry(saved_geo)
        else:
            self.resize(930, 680)

        self.load_memes()
        self.apply_view_mode()
        self.start_sync()

    def reconnect_session(self):
        reply = QMessageBox.question(
            self,
            "Reconnect Session",
            "Are you sure you want to refresh your iCloud session?\n\nA new 2FA authentication code will be sent to your device.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        term = None
        for t in ["konsole", "kitty", "alacritty", "foot", "xterm"]:
            if shutil.which(t):
                term = t
                break

        if not term:
            self.status_label.setText("Error: Terminal emulator not found.")
            return

        script_cmd = (
            "echo '===========================================';"
            "echo '       iCloud Session Reconnect (2FA)      ';"
            "echo '===========================================\\n';"
            "echo 'Please enter the 6-digit code sent to your device.\\n';"
            "rclone config reconnect icloud:;"
            "echo '\\n-------------------------------------------';"
            "echo 'Finished! Press Enter to close this window...';"
            "read -r"
        )

        if term == "konsole":
            proc = subprocess.Popen([term, "--title", "iCloud Session Reconnect", "-e", "sh", "-c", script_cmd])
        else:
            proc = subprocess.Popen([term, "-e", "sh", "-c", script_cmd])

        self.auth_watcher = ProcessWatcher(proc)
        self.auth_watcher.watcher_done.connect(self.on_auth_done)
        self.auth_watcher.start()

    def on_auth_done(self):
        self.status_label.setText("Session refreshed, syncing...")
        self.start_sync()

    def toggle_view_mode(self):
        self.view_mode = "list" if self.view_mode == "grid" else "grid"
        self.settings.setValue("view_mode", self.view_mode)
        self.apply_view_mode()

    def apply_view_mode(self):
        if self.view_mode == "grid":
            self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
            self.list_widget.setWordWrap(True)
            self.view_btn.setText("☰")
            self.view_btn.setToolTip("Switch to List View")

            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                raw_name = item.toolTip()
                item.setText(format_to_3_lines(raw_name, chars_per_line=18))
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

            self.zoom_slider.setEnabled(True)
            self.zoom_in_btn.setEnabled(True)
            self.zoom_out_btn.setEnabled(True)
            self.adjust_grid()
        else:
            self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
            self.list_widget.setGridSize(QSize())
            self.list_widget.setIconSize(QSize(48, 48))
            self.list_widget.setWordWrap(False)
            self.view_btn.setText("⊞")
            self.view_btn.setToolTip("Switch to Grid View")

            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                item.setText(item.toolTip())
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self.zoom_slider.setEnabled(False)
            self.zoom_in_btn.setEnabled(False)
            self.zoom_out_btn.setEnabled(False)

    def update_status_text(self):
        count = self.list_widget.count()
        if self.last_sync_time:
            text = f"{count} memes • {self.last_sync_msg} ({self.last_sync_time})"
        else:
            text = f"{count} memes • {self.last_sync_msg}"
        self.status_label.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.view_mode == "grid":
            self.adjust_grid()
        self.settings.setValue("geometry", self.saveGeometry())

    def on_zoom_changed(self, val):
        self.settings.setValue("zoom", val)
        if self.view_mode == "grid":
            self.adjust_grid()

    def adjust_grid(self):
        if self.view_mode != "grid":
            return

        viewport_w = self.list_widget.viewport().width()
        if viewport_w < 100:
            return

        zoom = self.zoom_slider.value()
        base_w = zoom + 36

        cols = max(1, viewport_w // base_w)
        cell_w = (viewport_w - 4) // cols
        cell_h = int(zoom * 0.88) + 78

        self.list_widget.setIconSize(QSize(zoom, int(zoom * 0.88)))
        self.list_widget.setGridSize(QSize(cell_w, cell_h))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.list_widget.currentItem()
            if item:
                self.copy_and_hide(item)
                return
        super().keyPressEvent(event)

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        file_path = Path(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)

        copy_act = menu.addAction("Copy Image")
        copy_act.triggered.connect(lambda: self.copy_and_hide(item))

        view_act = menu.addAction("View Image")
        view_act.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path))))

        folder_act = menu.addAction("Show in File Manager")
        folder_act.triggered.connect(lambda: self.show_in_dolphin(file_path))

        menu.exec(self.list_widget.viewport().mapToGlobal(pos))

    def show_in_dolphin(self, file_path):
        if shutil.which("dolphin"):
            subprocess.Popen(["dolphin", "--select", str(file_path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path.parent)))

    def open_meme_folder(self):
        LOCAL_MEME_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOCAL_MEME_DIR)))

    def start_sync(self):
        if self.sync_worker and self.sync_worker.isRunning():
            return
        self.last_sync_msg = "Syncing..."
        self.update_status_text()
        self.refresh_btn.setEnabled(False)
        self.sync_worker = BiSyncWorker()
        self.sync_worker.sync_finished.connect(self.on_sync_finished)
        self.sync_worker.start()

    def on_sync_finished(self, success, msg):
        self.refresh_btn.setEnabled(True)
        self.last_sync_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        self.last_sync_msg = msg
        self.load_memes()
        self.apply_view_mode()
        self.update_status_text()

    def load_memes(self):
        if self.thumb_worker and self.thumb_worker.isRunning():
            self.thumb_worker.stop()
            self.thumb_worker.wait()

        self.list_widget.clear()
        self.item_map.clear()

        LOCAL_MEME_DIR.mkdir(parents=True, exist_ok=True)

        files = [p for p in LOCAL_MEME_DIR.iterdir() if p.suffix.lower() in SUPPORTED_EXTS]
        default_icon = get_app_icon()

        for p in files:
            raw_name = p.stem.replace("-", " ").replace("_", " ")
            if self.view_mode == "grid":
                display_name = format_to_3_lines(raw_name, chars_per_line=18)
                align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
            else:
                display_name = raw_name
                align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

            item = QListWidgetItem(default_icon, display_name)
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            item.setToolTip(raw_name)
            item.setTextAlignment(align)
            self.list_widget.addItem(item)
            self.item_map[str(p)] = item

        self.update_status_text()

        self.thumb_worker = ThumbnailLoader(files)
        self.thumb_worker.thumb_ready.connect(self.update_thumbnail)
        self.thumb_worker.start()

    def update_thumbnail(self, path, pixmap):
        if path in self.item_map:
            self.item_map[path].setIcon(QIcon(pixmap))

    def filter_memes(self, text):
        raw_words = text.strip().split()
        if not raw_words:
            for i in range(self.list_widget.count()):
                self.list_widget.item(i).setHidden(False)
            return

        search_words = [normalize_text(w) for w in raw_words]

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            normalized_name = normalize_text(item.toolTip())
            match = all(w in normalized_name for w in search_words)
            item.setHidden(not match)

    def copy_and_hide(self, item):
        file_path = Path(item.data(Qt.ItemDataRole.UserRole))
        path_str = str(file_path)

        img = QImage(path_str)
        if not img.isNull():
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buffer, "PNG")
            png_bytes = bytes(buffer.data())

            if shutil.which("wl-copy"):
                try:
                    proc = subprocess.Popen(["wl-copy", "--type", "image/png"], stdin=subprocess.PIPE)
                    proc.communicate(input=png_bytes)
                except Exception as e:
                    print("wl-copy error:", e)

            clipboard = QApplication.clipboard()
            clipboard.setImage(img)

        QTimer.singleShot(350, self.hide)

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.search_bar.clear()
                self.list_widget.clearSelection()
                self.list_widget.scrollToTop()
                self.update_status_text()
                self.show()
                self.raise_()
                self.activateWindow()
                self.search_bar.setFocus()
                if self.view_mode == "grid":
                    QTimer.singleShot(20, self.adjust_grid)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Meme Picker")
    app.setApplicationDisplayName("Meme Picker")
    app.setDesktopFileName("meme-picker")
    app.setQuitOnLastWindowClosed(False)

    picker = MemePicker()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
