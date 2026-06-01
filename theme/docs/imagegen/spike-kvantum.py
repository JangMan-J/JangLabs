#!/usr/bin/env python3
"""Throwaway spike: prove real headless Kvantum widget rendering -> PNG."""
import sys
from PySide6 import QtWidgets, QtGui, QtCore

Role = QtGui.QPalette.ColorRole


def build(theme_label):
    w = QtWidgets.QWidget()
    w.setWindowTitle("Kvantum render spike")
    w.setAutoFillBackground(True)
    outer = QtWidgets.QVBoxLayout(w)
    outer.setContentsMargins(16, 16, 16, 16)
    outer.setSpacing(10)

    head = QtWidgets.QLabel(f"Kvantum gallery — {theme_label}")
    hf = head.font(); hf.setPointSize(14); hf.setBold(True); head.setFont(hf)
    outer.addWidget(head)

    brow = QtWidgets.QHBoxLayout()
    ok = QtWidgets.QPushButton("OK"); ok.setDefault(True)
    cancel = QtWidgets.QPushButton("Cancel")
    disabled = QtWidgets.QPushButton("Disabled"); disabled.setEnabled(False)
    flat = QtWidgets.QPushButton("Flat"); flat.setFlat(True)
    for b in (ok, cancel, disabled, flat):
        brow.addWidget(b)
    brow.addStretch(1)
    outer.addLayout(brow)

    irow = QtWidgets.QHBoxLayout()
    chk = QtWidgets.QCheckBox("Enabled"); chk.setChecked(True)
    chk2 = QtWidgets.QCheckBox("Off")
    rad = QtWidgets.QRadioButton("Selected"); rad.setChecked(True)
    rad2 = QtWidgets.QRadioButton("Other")
    combo = QtWidgets.QComboBox(); combo.addItems(["Catppuccin", "Arc Dark", "Nordic"])
    spin = QtWidgets.QSpinBox(); spin.setValue(42)
    for x in (chk, chk2, rad, rad2, combo, spin):
        irow.addWidget(x)
    irow.addStretch(1)
    outer.addLayout(irow)

    le = QtWidgets.QLineEdit(); le.setPlaceholderText("search…"); le.setText("editable field")
    outer.addWidget(le)
    sld = QtWidgets.QSlider(QtCore.Qt.Horizontal); sld.setRange(0, 100); sld.setValue(65)
    outer.addWidget(sld)
    pb = QtWidgets.QProgressBar(); pb.setValue(45)
    outer.addWidget(pb)

    tabs = QtWidgets.QTabWidget()
    tree = QtWidgets.QTreeWidget(); tree.setHeaderLabels(["Name", "Size"])
    for i in range(1, 6):
        tree.addTopLevelItem(QtWidgets.QTreeWidgetItem([f"document-{i}.txt", f"{i*3} KB"]))
    tree.setCurrentItem(tree.topLevelItem(1))
    tabs.addTab(tree, "Files")
    form_host = QtWidgets.QWidget(); form = QtWidgets.QFormLayout(form_host)
    form.addRow("Name:", QtWidgets.QLineEdit("theme"))
    form.addRow("Accent:", QtWidgets.QComboBox())
    tabs.addTab(form_host, "Settings")
    outer.addWidget(tabs, 1)

    gb = QtWidgets.QGroupBox("Group box")
    gl = QtWidgets.QHBoxLayout(gb)
    mb = QtWidgets.QPushButton("Menu ▾")
    menu = QtWidgets.QMenu(mb)
    for label in ("Action one", "Action two"):
        menu.addAction(label)
    menu.addSeparator(); menu.addAction("Quit")
    mb.setMenu(menu)
    gl.addWidget(mb); gl.addWidget(QtWidgets.QCheckBox("option")); gl.addStretch(1)
    outer.addWidget(gb)

    w.resize(860, 620)
    return w


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/kvantum-spike.png"
    theme = sys.argv[2] if len(sys.argv) > 2 else "(active)"
    app = QtWidgets.QApplication(["spike"])
    pal = app.palette()
    print("STYLE:", app.style().objectName())
    print("WINDOW:", pal.color(Role.Window).name())
    print("WINDOWTEXT:", pal.color(Role.WindowText).name())
    print("BASE:", pal.color(Role.Base).name())
    print("HIGHLIGHT:", pal.color(Role.Highlight).name())
    w = build(theme)
    w.show()
    for _ in range(5):
        app.processEvents()
    pm = w.grab()
    ok = pm.save(out)
    print("SAVED:", ok, out, pm.width(), "x", pm.height())


main()
