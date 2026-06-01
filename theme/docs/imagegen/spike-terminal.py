#!/usr/bin/env python3
"""Spike: emit a mini terminal scene as 24-bit truecolor ANSI (Catppuccin Mocha)."""
import sys


def fg(h):
    h = h.lstrip('#'); return f"\x1b[38;2;{int(h[0:2],16)};{int(h[2:4],16)};{int(h[4:6],16)}m"


def bg(h):
    h = h.lstrip('#'); return f"\x1b[48;2;{int(h[0:2],16)};{int(h[2:4],16)};{int(h[4:6],16)}m"


R = "\x1b[0m"; B = "\x1b[1m"
text = "#cdd6f4"; green = "#a6e3a1"; blue = "#89b4fa"; mauve = "#cba6f7"
teal = "#94e2d5"; yellow = "#f9e2af"; red = "#f38ba8"; pink = "#f5c2e7"; sub = "#a6adc8"

L = []
L.append(f"{fg(green)}{B}user{R}{fg(text)}@{fg(green)}{B}cachyos{R} {fg(blue)}{B}~/JangLabs/theme{R} {fg(mauve)} main{R}")
L.append(f"{fg(text)}$ eza --icons --git{R}")
L.append(f"{fg(blue)}{B}drwxr-xr-x{R}{fg(sub)}   - {fg(teal)}derived{R}")
L.append(f"{fg(sub)}.rw-r--r--{R}{fg(sub)} 1.2k {fg(green)}README.md{R}")
L.append(f"{fg(sub)}.rwxr-xr-x{R}{fg(sub)} 4.0k {fg(green)}render-kvantum.py{R}")
L.append(f"{fg(sub)}.rw-r--r--{R}{fg(sub)}  812 {fg(yellow)}fixtures.json{R}")
L.append("")
L.append(f"{fg(blue)}{B}  OS{R}{fg(sub)}: CachyOS x86_64{R}")
L.append(f"{fg(mauve)}{B}  DE{R}{fg(sub)}: KDE Plasma 6{R}")
L.append(f"{fg(teal)}{B}  Theme{R}{fg(sub)}: catppuccin-mocha-sapphire{R}")
L.append(f"{fg(red)}{B}  Term{R}{fg(sub)}: kitty{R}")
L.append("")
ramp = ["#45475a", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#f5c2e7",
        "#94e2d5", "#bac2de", "#585b70", "#f38ba8", "#a6e3a1", "#f9e2af",
        "#89b4fa", "#f5c2e7", "#94e2d5", "#a6adc8"]
line = "".join(fg(c) + "███" for c in ramp) + R
L.append(line)
sys.stdout.write("\n".join(L) + "\n")
