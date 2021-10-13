#! /usr/bin/env python3
import ctypes
import imghdr
import os
import platform
import random
import subprocess
import sys
from typing import Optional

from PyQt5 import QtWidgets, QtGui, QtCore

if platform.system() == "Linux":
    import dbus
    import dbus.mainloop.glib
    import dbus.service
else:
    dbus = None


class Wallpaper:
    def __init__(self, file_path):
        self.file_path = file_path

    def is_valid(self) -> bool:
        return imghdr.what(self.file_path) is not None

    def set_active_linux(self) -> None:
        desktop_session = os.environ.get("DESKTOP_SESSION")

        if desktop_session is not None:
            desktop_session = desktop_session.lower()

            if desktop_session in ["gnome", "gnome-wayland", "unity", "ubuntu", "pantheon", "budgie-desktop", "pop"]:
                subprocess.call(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", QtCore.QUrl.fromLocalFile(self.file_path).toString()])
            elif desktop_session in ["cinnamon"]:
                subprocess.call(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", QtCore.QUrl.fromLocalFile(self.file_path).toString()])
            elif desktop_session in ["mate"]:
                subprocess.call(["gsettings", "set", "org.mate.background", "picture-filename", QtCore.QUrl.fromLocalFile(self.file_path).toString()])
            elif desktop_session in ["plasma", "kde"]:
                # TODO: Implement support for KDE
                pass

    def set_active_macos(self) -> None:
        script = """
            /usr/bin/osascript<<END
            tell application "Finder"
            set desktop picture to POSIX file "{}"
            end tell
            END
        """

        subprocess.Popen(script.format(self.file_path), shell=True)

    def set_active_windows(self) -> None:
        ctypes.windll.user32.SystemParametersInfoW(20, 0, self.file_path, 0)

    def set_active(self) -> None:
        if platform.system() == "Windows":
            self.set_active_windows()
            pass
        elif platform.system() == "Darwin":
            self.set_active_macos()
            pass
        else:
            self.set_active_linux()


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


if dbus:
    class DBusHandler(dbus.service.Object):
        def __init__(self, main_window: "MainWindow", session_bus: dbus.Bus):
            dbus.service.Object.__init__(self, session_bus, "/")

            self.main_window = main_window

        @dbus.service.method("com.selfcoders.WallpaperChanger", in_signature="", out_signature="")
        def toggle_pause(self):
            self.main_window.toggle_pause()

        @dbus.service.method("com.selfcoders.WallpaperChanger", in_signature="", out_signature="")
        def previous_wallpaper(self):
            self.main_window.previous_wallpaper()

        @dbus.service.method("com.selfcoders.WallpaperChanger", in_signature="", out_signature="")
        def next_wallpaper(self):
            self.main_window.next_wallpaper()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dbus_session):
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
        self.interval_field.setSuffix(" min")
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
        tray_menu.addAction(self.style().standardIcon(QtWidgets.QStyle.SP_MediaSkipBackward), "Previous wallpaper", self.previous_wallpaper)
        self.toggle_pause_action = tray_menu.addAction("", self.toggle_pause)
        tray_menu.addAction(self.style().standardIcon(QtWidgets.QStyle.SP_MediaSkipForward), "Next wallpaper", self.next_wallpaper)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", self.quit)

        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.handle_tray_icon_activation)
        self.tray_icon.show()

        self.load_settings()

        self.update_pause_action()

        if dbus_session:
            DBusHandler(self, dbus_session)

    def handle_tray_icon_activation(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.close()
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

        if platform.system() == "Linux":
            subprocess.call(["xdg-open", wallpaper.file_path])
        elif platform.system() == "Darwin":
            subprocess.call(["open", wallpaper.file_path])
        elif platform.system() == "Windows":
            os.startfile(wallpaper.file_path)

    def update_pause_action(self):
        if self.timer.isActive():
            self.toggle_pause_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
            self.toggle_pause_action.setText("Pause")
        else:
            self.toggle_pause_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
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

        wallpaper.set_active()

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
    app.setWindowIcon(app.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))

    if dbus:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        session_bus = dbus.SessionBus()
        bus = dbus.service.BusName("com.selfcoders.WallpaperChanger", session_bus)
    else:
        session_bus = None

    main_window = MainWindow(session_bus)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
