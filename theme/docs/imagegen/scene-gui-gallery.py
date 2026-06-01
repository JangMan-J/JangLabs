#!/usr/bin/env python3
"""Dense GUI scene: a reproduction of the official Qt "Widgets Gallery" layout
(4 group boxes — radios/checks, push buttons, a table+text-edit tab widget, and a
full input column with line edit/spin/date/slider/scrollbar/dial — plus a progress
bar). Real Qt widgets painted by the real Kvantum engine (offscreen), so occupancy
is balanced across many widget colors instead of being background-dominated.

Run:
  XDG_CONFIG_HOME=<tmp> QT_QPA_PLATFORM=offscreen QT_STYLE_OVERRIDE=kvantum \
  python scene-gui-gallery.py <out.png> [theme-label] [w] [h]
"""
import sys
from PySide6 import QtWidgets as Q, QtGui, QtCore


class WidgetGallery(Q.QDialog):
    def __init__(self, theme_label):
        super().__init__()
        self._top_left()
        self._top_right()
        self._bottom_left()
        self._bottom_right()
        self.progress = Q.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(63)

        top = Q.QHBoxLayout()
        top.addWidget(Q.QLabel("Style:"))
        style_combo = Q.QComboBox()
        style_combo.addItems(["Kvantum", "Fusion", "Windows"])
        top.addWidget(style_combo)
        top.addStretch(1)
        cb_pal = Q.QCheckBox("Use style's standard palette"); cb_pal.setChecked(True)
        top.addWidget(cb_pal)
        top.addWidget(Q.QCheckBox("Disable widgets"))

        grid = Q.QGridLayout()
        grid.addLayout(top, 0, 0, 1, 2)
        grid.addWidget(self.tl, 1, 0)
        grid.addWidget(self.tr, 1, 1)
        grid.addWidget(self.bl, 2, 0)
        grid.addWidget(self.br, 2, 1)
        grid.addWidget(self.progress, 3, 0, 1, 2)
        grid.setRowStretch(1, 0)   # top groups collapse to fit their content
        grid.setRowStretch(2, 1)   # table + inputs absorb the height
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.setLayout(grid)
        self.setWindowTitle(f"Widgets Gallery — {theme_label}")

    def _top_left(self):
        self.tl = Q.QGroupBox("Group 1")
        r1 = Q.QRadioButton("Radio button 1"); r1.setChecked(True)
        r2 = Q.QRadioButton("Radio button 2")
        r3 = Q.QRadioButton("Radio button 3")
        chk = Q.QCheckBox("Tri-state check box"); chk.setTristate(True)
        chk.setCheckState(QtCore.Qt.PartiallyChecked)
        lay = Q.QVBoxLayout()
        for w in (r1, r2, r3, chk):
            lay.addWidget(w)
        lay.addStretch(1)
        self.tl.setLayout(lay)

    def _top_right(self):
        self.tr = Q.QGroupBox("Group 2")
        default = Q.QPushButton("Default Push Button"); default.setDefault(True)
        toggle = Q.QPushButton("Toggle Push Button"); toggle.setCheckable(True); toggle.setChecked(True)
        flat = Q.QPushButton("Flat Push Button"); flat.setFlat(True)
        cmd = Q.QCommandLinkButton("Command Link", "Description text")
        lay = Q.QVBoxLayout()
        for w in (default, toggle, flat, cmd):
            lay.addWidget(w)
        lay.addStretch(1)
        self.tr.setLayout(lay)

    def _bottom_left(self):
        self.bl = Q.QTabWidget()
        tab1 = Q.QWidget()
        table = Q.QTableWidget(8, 3)
        table.setHorizontalHeaderLabels(["Name", "Size", "Type"])
        data = [("derived", "—", "Folder"), ("docs", "—", "Folder"),
                ("README.md", "2.1 KB", "Markdown"), ("CLAUDE.md", "1.2 KB", "Markdown"),
                ("scene.py", "4.0 KB", "Python"), ("fixtures.json", "812 B", "JSON"),
                ("notes.txt", "48 B", "Text"), ("theme.kvconfig", "1.6 KB", "Config")]
        for r, row in enumerate(data):
            for c, val in enumerate(row):
                table.setItem(r, c, Q.QTableWidgetItem(val))
        table.setCurrentCell(4, 0)            # one selected row -> accent
        table.resizeColumnsToContents()
        l1 = Q.QVBoxLayout(); l1.addWidget(table); l1.setContentsMargins(6, 6, 6, 6)
        tab1.setLayout(l1)

        tab2 = Q.QWidget()
        edit = Q.QTextEdit()
        edit.setPlainText(
            "Twinkle, twinkle, little star,\nHow I wonder what you are.\n"
            "Up above the world so high,\nLike a diamond in the sky.\n\n"
            "def fingerprint(scene):\n    return histogram(scene.pixels)\n")
        l2 = Q.QVBoxLayout(); l2.addWidget(edit); l2.setContentsMargins(6, 6, 6, 6)
        tab2.setLayout(l2)

        self.bl.addTab(tab1, "Table")
        self.bl.addTab(tab2, "Text Edit")

    def _bottom_right(self):
        self.br = Q.QGroupBox("Group 3"); self.br.setCheckable(True); self.br.setChecked(True)
        line = Q.QLineEdit("editable text field")
        spin = Q.QSpinBox(); spin.setValue(50)
        dt = Q.QDateTimeEdit(); dt.setCalendarPopup(True)
        slider = Q.QSlider(QtCore.Qt.Horizontal); slider.setValue(40)
        scroll = Q.QScrollBar(QtCore.Qt.Horizontal); scroll.setValue(60)
        dial = Q.QDial(); dial.setValue(30); dial.setNotchesVisible(True)
        items = Q.QListWidget()
        for name in ("Profile: default", "Profile: dark", "Profile: high-contrast",
                     "Profile: solarized", "Profile: custom"):
            Q.QListWidgetItem(name, items)
        items.setCurrentRow(1)
        grid = Q.QGridLayout()
        grid.addWidget(line, 0, 0)
        grid.addWidget(spin, 1, 0)
        grid.addWidget(dt, 2, 0)
        grid.addWidget(slider, 3, 0)
        grid.addWidget(scroll, 4, 0)
        grid.addWidget(dial, 0, 1, 5, 1)
        grid.addWidget(items, 5, 0, 1, 2)   # fills Group 3's leftover height
        grid.setRowStretch(5, 1)
        self.br.setLayout(grid)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/scene-gui-gallery.png"
    theme = sys.argv[2] if len(sys.argv) > 2 else "(active)"
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    h = int(sys.argv[4]) if len(sys.argv) > 4 else 800
    app = Q.QApplication(["gallery"])
    g = WidgetGallery(theme)
    g.resize(w, h)
    g.show()
    for _ in range(6):
        app.processEvents()
    ok = g.grab().save(out)
    print("STYLE:", app.style().objectName(), "saved:", ok, out, g.width(), "x", g.height())


main()
