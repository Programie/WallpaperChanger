#! /usr/bin/env python3
import imghdr
import os
import random
import subprocess
import sys
from typing import Optional

from PyQt5 import QtWidgets, QtGui, QtCore


class Wallpaper:
    def __init__(self, file_path):
        self.file_path = file_path

    def is_valid(self) -> bool:
        return imghdr.what(self.file_path) is not None


class WallpaperList(list):
    def __init__(self):
        super().__init__()

        self.current_index = 0

    def add_from_path(self, path: str) -> None:
        for current_path, folders, files in os.walk(path):
            for file in files:
                self.append(Wallpaper(os.path.join(current_path, file)))

        random.shuffle(self)

    def previous(self) -> bool:
        for try_no in range(10):
            if self.current_index <= 0:
                self.current_index = len(self) - 1
            else:
                self.current_index -= 1

            if self.get_current().is_valid():
                return True

        return False

    def next(self) -> bool:
        for try_no in range(10):
            if self.current_index >= len(self) - 1:
                self.current_index = 0
            else:
                self.current_index += 1

            if self.get_current().is_valid():
                return True

        return False

    def get_current(self) -> Optional[Wallpaper]:
        if not len(self):
            return None

        if self.current_index > len(self) - 1:
            self.current_index = 0

        return self[self.current_index]


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.wallpapers = WallpaperList()
        self.current_wallpaper_index = 0

        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.next_wallpaper)

        self.setFixedWidth(500)
        self.setFixedHeight(150)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(layout)

        form_container = QtWidgets.QWidget()
        layout.addWidget(form_container)

        form_layout = QtWidgets.QGridLayout()
        form_container.setLayout(form_layout)

        form_layout.addWidget(QtWidgets.QLabel("Folder:"), 0, 0)

        self.folder_field = QtWidgets.QLineEdit()
        self.folder_field.setReadOnly(True)
        form_layout.addWidget(self.folder_field, 0, 1)

        browse_folder_button = QtWidgets.QPushButton("Browse")
        browse_folder_button.clicked.connect(self.browse_folder)
        form_layout.addWidget(browse_folder_button, 0, 2)

        form_layout.addWidget(QtWidgets.QLabel("Interval:"), 1, 0)

        self.interval_field = QtWidgets.QSpinBox()
        self.interval_field.setMinimum(1)
        self.interval_field.setMaximum(10000)
        form_layout.addWidget(self.interval_field, 1, 1)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        button_box.accepted.connect(self.save)
        button_box.rejected.connect(self.close)

        tray_menu = QtWidgets.QMenu()

        tray_menu.addAction(QtGui.QIcon.fromTheme("preferences"), "Show settings", self.show)
        tray_menu.addSeparator()
        tray_menu.addAction(QtGui.QIcon.fromTheme("image-viewer"), "Open current wallpaper", self.open_wallpaper)
        tray_menu.addSeparator()
        tray_menu.addAction(QtGui.QIcon.fromTheme("media-skip-backward"), "Previous wallpaper", self.previous_wallpaper)
        self.toggle_pause_action = tray_menu.addAction("", self.toggle_pause)
        tray_menu.addAction(QtGui.QIcon.fromTheme("media-skip-forward"), "Next wallpaper", self.next_wallpaper)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", self.quit)

        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.handle_tray_icon_activation)
        self.tray_icon.show()

        self.load_settings()

        self.update_pause_action()

    def handle_tray_icon_activation(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def quit(self):
        QtGui.QGuiApplication.quit()

    def browse_folder(self):
        new_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder with pictures", self.folder_field.text())

        if new_folder:
            self.folder_field.setText(new_folder)

    def open_wallpaper(self):
        wallpaper = self.wallpapers.get_current()

        if wallpaper is None:
            return

        subprocess.call(["xdg-open", wallpaper.file_path])

    def update_pause_action(self):
        if self.timer.isActive():
            self.toggle_pause_action.setIcon(QtGui.QIcon.fromTheme("media-playback-pause"))
            self.toggle_pause_action.setText("Pause")
        else:
            self.toggle_pause_action.setIcon(QtGui.QIcon.fromTheme("media-playback-start"))
            self.toggle_pause_action.setText("Continue")

    def toggle_pause(self):
        if self.timer.isActive():
            self.timer.stop()
        else:
            self.timer.start()

        self.update_pause_action()

    def previous_wallpaper(self):
        if self.wallpapers.previous():
            self.update_wallpaper()

    def next_wallpaper(self):
        if self.wallpapers.next():
            self.update_wallpaper()

    def update_wallpaper(self):
        wallpaper = self.wallpapers.get_current()

        if wallpaper is None:
            return

        self.tray_icon.setToolTip("{}\n\nCurrent wallpaper: {}".format(QtGui.QGuiApplication.applicationName(), wallpaper.file_path))

        subprocess.call(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", QtCore.QUrl.fromLocalFile(wallpaper.file_path).toString()])

        self.timer.start()

        self.update_pause_action()

    def reload_wallpapers(self):
        path = self.folder_field.text()

        if not path:
            return

        self.wallpapers.clear()
        self.wallpapers.add_from_path(path)

        self.next_wallpaper()
        self.timer.setInterval(self.interval_field.value() * 1000 * 60)
        self.timer.start()

        self.update_pause_action()

    def save(self):
        settings = QtCore.QSettings("SelfCoders", "WallpaperChanger")

        settings.setValue("folder", self.folder_field.text())
        settings.setValue("interval", self.interval_field.value())

        self.close()

    def load_settings(self):
        settings = QtCore.QSettings("SelfCoders", "WallpaperChanger")

        self.folder_field.setText(settings.value("folder"))
        self.interval_field.setValue(int(settings.value("interval", 1)))

        self.reload_wallpapers()

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.load_settings()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Wallpaper Changer")
    app.setWindowIcon(QtGui.QIcon.fromTheme("wallpaper"))

    main_window = MainWindow()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
