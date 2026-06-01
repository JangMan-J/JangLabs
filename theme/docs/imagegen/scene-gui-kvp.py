#!/usr/bin/env python3
"""KvantumPreview-style GUI scene, rendered in-process through the REAL Kvantum
engine (offscreen). Pixels are produced by libkvantum.so — identical to the
kvantumpreview binary; only the layout is reconstructed here, which lets us force
widget states (hover/pressed/toggled/disabled) deterministically and grab the
result headlessly. This is the comprehensive "coverage" scene.

Run:
  XDG_CONFIG_HOME=<tmp> QT_QPA_PLATFORM=offscreen QT_STYLE_OVERRIDE=kvantum \
  python scene-gui-kvp.py <out.png> [theme-label] [w] [h]
"""
import sys
from PySide6 import QtWidgets as Q, QtGui, QtCore

UM = QtCore.Qt.WA_UnderMouse


def button_set(disabled):
    col = Q.QVBoxLayout()
    simple = Q.QPushButton("Simple push button")
    toggle = Q.QPushButton("Toggle push button"); toggle.setCheckable(True); toggle.setChecked(True)
    multi = Q.QPushButton("Multi-line\npush button")
    icon = Q.QPushButton("Push button\nwith 32px folder icon")
    ic = QtGui.QIcon.fromTheme("folder")
    if not ic.isNull():
        icon.setIcon(ic); icon.setIconSize(QtCore.QSize(32, 32))
    default = Q.QPushButton("Default\npush button"); default.setDefault(True); default.setAutoDefault(True)
    btns = [simple, toggle, multi, icon, default]
    for b in btns:
        b.setMinimumHeight(46)
        b.setEnabled(not disabled)
        col.addWidget(b)
    return col, default


def push_buttons_tab():
    page = Q.QWidget(); v = Q.QVBoxLayout(page)
    top = Q.QHBoxLayout(); top.addStretch(1)
    top.addWidget(Q.QCheckBox("Flat buttons")); top.addStretch(1)
    v.addLayout(top)

    grid = Q.QHBoxLayout()
    left, left_default = button_set(disabled=False)
    left_default.setObjectName("hoverTarget")        # replicate the user's hover
    grid.addLayout(left)

    mid = Q.QVBoxLayout()
    tall = Q.QPushButton("Toggle\npush\nbutton\n\nwith\nheight\ngreater\nthan\nwidth")
    tall.setCheckable(True); tall.setChecked(True)
    tall.setMinimumHeight(230); tall.setMaximumWidth(120)
    mid.addWidget(tall); mid.addStretch(1)
    grid.addLayout(mid)

    right, _ = button_set(disabled=True)
    grid.addLayout(right)
    v.addLayout(grid)

    mrow = Q.QHBoxLayout(); mrow.addStretch(1)
    mbtn = Q.QPushButton("Push button with menu")
    menu = Q.QMenu(mbtn)
    for a in ("Action one", "Action two", "Quit"):
        menu.addAction(a)
    mbtn.setMenu(menu); mrow.addWidget(mbtn); mrow.addStretch(1)
    v.addLayout(mrow)
    v.addStretch(1)

    lbl = Q.QLabel("Button Box"); lbl.setAlignment(QtCore.Qt.AlignCenter)
    f = lbl.font(); f.setBold(True); lbl.setFont(f); v.addWidget(lbl)
    bb = Q.QDialogButtonBox()
    bb.addButton("Yes", Q.QDialogButtonBox.YesRole)
    bb.addButton("No", Q.QDialogButtonBox.NoRole)
    ok = bb.addButton(Q.QDialogButtonBox.Ok)
    bb.addButton(Q.QDialogButtonBox.Save)
    bb.addButton(Q.QDialogButtonBox.Open)
    bb.addButton(Q.QDialogButtonBox.Apply)
    bb.addButton(Q.QDialogButtonBox.Cancel)
    ok.setDefault(True)
    v.addWidget(bb)
    return page


def build(theme_label):
    win = Q.QMainWindow()
    win.setWindowTitle(f"Kvantum Preview — {theme_label}")
    win.menuBar().addMenu("File").addAction("Quit")

    central = Q.QWidget(); cv = Q.QVBoxLayout(central)

    row = Q.QHBoxLayout()
    row.addWidget(Q.QPushButton("Quit"))
    row.addWidget(Q.QPushButton("Toggle Layout"))
    dm = Q.QPushButton("Doc Mode"); dm.setCheckable(True); dm.setChecked(True); row.addWidget(dm)
    menu_btn = Q.QPushButton("Menu Button"); mm = Q.QMenu(menu_btn); mm.addAction("x"); menu_btn.setMenu(mm); row.addWidget(menu_btn)
    combo = Q.QComboBox(); combo.addItems(["Kvantum", "KvArcDark", "Nordic"]); row.addWidget(combo)
    row.addWidget(Q.QLineEdit("Kvantum"))
    sp = Q.QSpinBox(); sp.setValue(0); row.addWidget(sp)
    cv.addLayout(row)

    row2 = Q.QHBoxLayout()
    row2.addWidget(Q.QDateTimeEdit())
    pb = Q.QProgressBar(); pb.setValue(50); row2.addWidget(pb, 1)
    cv.addLayout(row2)

    tabs = Q.QTabWidget()
    tabs.addTab(push_buttons_tab(), "Push buttons")
    for name in ("Tool buttons", "Radio/Check buttons", "Combos/Spins/Inputs",
                 "Sliders/Scrolls/Progress/Dial", "Containers"):
        tabs.addTab(Q.QWidget(), name)
    cv.addWidget(tabs, 1)

    win.setCentralWidget(central)
    return win


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/scene-gui-kvp.png"
    theme = sys.argv[2] if len(sys.argv) > 2 else "(active)"
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    h = int(sys.argv[4]) if len(sys.argv) > 4 else 900
    app = Q.QApplication(["kvp"])
    win = build(theme)
    win.resize(w, h)
    win.show()
    for _ in range(8):
        app.processEvents()
    # force hover AFTER the event loop settles, right before grabbing.
    # Kvantum tracks hover via real Hover events, so synthesize them (not just WA_UnderMouse).
    t = win.findChild(Q.QPushButton, "hoverTarget")
    if t:
        t.setAttribute(QtCore.Qt.WA_Hover, True)
        t.setAttribute(UM, True)
        c = t.rect().center(); cf = QtCore.QPointF(c)
        gf = QtCore.QPointF(t.mapToGlobal(c))
        app.sendEvent(t, QtGui.QEnterEvent(cf, cf, gf))
        app.sendEvent(t, QtGui.QHoverEvent(QtCore.QEvent.Type.HoverEnter, cf, QtCore.QPointF(-1, -1)))
        app.sendEvent(t, QtGui.QHoverEvent(QtCore.QEvent.Type.HoverMove, cf, cf))
        app.processEvents()
        print("hoverTarget.underMouse() =", t.underMouse())
    ok = win.grab().save(out)
    print("STYLE:", app.style().objectName(), "saved:", ok, out, win.width(), "x", win.height())


main()
