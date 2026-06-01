#!/usr/bin/env python3
"""Representative GUI scene: a realistic file-manager window rendered through the
real Kvantum engine (offscreen). Models realistic occupancy — dominant view/base
area, sidebar, toolbar, menubar, statusbar, and ONE accent (the selected row) —
rather than a wall of controls. This is the region that gets sampled for the
theme's color fingerprint.

Run:
  XDG_CONFIG_HOME=<tmp-with-Kvantum/kvantum.kvconfig> \
  QT_QPA_PLATFORM=offscreen QT_STYLE_OVERRIDE=kvantum \
  python scene-gui.py <out.png> [theme-label]
"""
import sys
from pathlib import Path
from PySide6 import QtWidgets, QtGui, QtCore


def build_window(theme_label):
    win = QtWidgets.QMainWindow()
    win.setWindowTitle(f"Files — {theme_label}")

    # Menu bar (window color + text)
    mb = win.menuBar()
    for m in ("File", "Edit", "View", "Go", "Help"):
        menu = mb.addMenu(m)
        menu.addAction("Item one"); menu.addAction("Item two")

    # Toolbar (button/toolbar surfaces + a location field)
    tb = QtWidgets.QToolBar(); tb.setMovable(False)
    for name in ("← Back", "Forward →", "↑ Up"):
        tb.addAction(QtGui.QAction(name, win))
    tb.addSeparator()
    loc = QtWidgets.QLineEdit(str(Path(__file__).resolve().parents[2]))
    loc.setMinimumWidth(380)
    tb.addWidget(loc)
    tb.addSeparator()
    for name in ("Icons", "Details"):
        tb.addAction(QtGui.QAction(name, win))
    win.addToolBar(tb)

    # Central: places sidebar + file view
    split = QtWidgets.QSplitter()

    sidebar = QtWidgets.QListWidget()
    for p in ("Home", "Desktop", "Documents", "Downloads", "Music",
              "Pictures", "Projects", "Trash"):
        QtWidgets.QListWidgetItem(p, sidebar)

    view = QtWidgets.QTreeWidget()
    view.setHeaderLabels(["Name", "Size", "Modified"])
    view.setRootIsDecorated(False)
    rows = [
        ("derived", "—", "13:15"), ("docs", "—", "13:15"),
        ("findings", "—", "12:30"), ("samples", "—", "11:02"),
        ("tools", "—", "12:47"), ("CLAUDE.md", "1.2 KB", "10:14"),
        ("HANDOFF.md", "3.4 KB", "12:58"), ("README.md", "2.1 KB", "12:58"),
        ("requirements.txt", "48 B", "09:31"), (".gitignore", "112 B", "08:20"),
    ]
    for n, s, m in rows:
        QtWidgets.QTreeWidgetItem(view, [n, s, m])
    view.setCurrentItem(view.topLevelItem(6))   # one selected row -> accent
    for i in range(view.columnCount()):
        view.resizeColumnToContents(i)

    split.addWidget(sidebar)
    split.addWidget(view)
    split.setStretchFactor(0, 0)
    split.setStretchFactor(1, 1)
    split.setSizes([180, 700])
    win.setCentralWidget(split)

    sb = win.statusBar()
    sb.showMessage("10 items (5 folders, 5 files) — 6.9 KB")

    win.resize(940, 580)
    return win


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/scene-gui.png"
    theme = sys.argv[2] if len(sys.argv) > 2 else "(active)"
    app = QtWidgets.QApplication(["scene"])
    win = build_window(theme)
    win.show()
    for _ in range(6):
        app.processEvents()
    ok = win.grab().save(out)
    print("STYLE:", app.style().objectName(), "| saved:", ok, out,
          win.width(), "x", win.height())


main()
