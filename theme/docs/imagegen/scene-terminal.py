#!/usr/bin/env python3
"""Terminal scene: a REAL fastfetch render, recolored to a terminal scheme.

We drive the actual `fastfetch` binary (real CachyOS logo art, real key/separator
styling, the native two-row 16-color blocks) with a curated, theme-appropriate
module set, then post-process its output for freeze:

  1. FLATTEN. fastfetch positions the info column beside the logo with cursor-move
     escapes (CUU `ESC[22A` to jump back to the top, CHA `ESC[1G`, CUF `ESC[57C`
     to indent past the logo). freeze does not interpret cursor motion, so we
     emulate a terminal cell grid and re-serialize the final screen as plain
     left-to-right lines (gaps become spaces). The side-by-side layout survives.

  2. RECOLOR. freeze has no ANSI-palette key, so we map every SGR color index to
     the scheme's 16-color palette and emit it as 24-bit truecolor (see
     PROGRESS.md "Terminal — freeze render"). A real Mocha terminal renders
     fastfetch's cyan/green logo as Mocha cyan(teal)/green — this reproduces that
     exactly, so the fingerprint measures the real on-screen palette.

  3. FRAME. Wrap the fastfetch block in a shell prompt (command above, cursor
     below) so it reads as a terminal session, not a floating render. No window
     chrome: a terminal's titlebar is painted by the GUI theme, not the scheme,
     and would distort the occupancy fingerprint (realism = data fidelity).

The native color blocks double as the palette **instrumentation strip**: every
ANSI color present for attribution/coverage, but the fingerprint extractor
excludes that region from the occupancy sample (occupancy != coverage).

Usage:  python scene-terminal.py > scene.ans
        freeze -b '#1e1e2e' -m 40 --font.size 28 -o raw.png < scene.ans
        magick raw.png -resize 1280x600 -background '#1e1e2e' \
               -gravity center -extent 1280x600 derived/previews/...png
"""
import json
import re
import shutil
import subprocess
import sys

# --- Catppuccin Mocha (calibration scheme) -------------------------------------
# Standard Mocha terminal ANSI palette: indices 0-15 (normal 0-7, bright 8-15).
PALETTE = [
    "#45475a", "#f38ba8", "#a6e3a1", "#f9e2af",  # black  red   green  yellow
    "#89b4fa", "#f5c2e7", "#94e2d5", "#bac2de",  # blue   pink  teal   subtext1
    "#585b70", "#f38ba8", "#a6e3a1", "#f9e2af",  # bblack bred  bgreen byellow
    "#89b4fa", "#f5c2e7", "#94e2d5", "#a6adc8",  # bblue  bpink bteal  subtext0
]
DEFAULT_FG = "#cdd6f4"  # Text  — default foreground
BASE_BG = "#1e1e2e"     # Base  — default background (set on freeze via -b)
# Prompt accents (also drawn from the scheme).
P_USER = "#a6e3a1"      # green
P_PATH = "#89b4fa"      # blue
P_GIT = "#cba6f7"       # mauve
P_ARROW = "#a6e3a1"     # green

LOGO = "CachyOS"        # pinned so the scene is deterministic on any host
TITLE_USER, TITLE_HOST = "user", "cachyos"

# Curated, theme-appropriate sysinfo (fixed -> reproducible artifact).
INFO = [
    ("OS", "CachyOS x86_64"),
    ("Kernel", "7.0.10-cachyos"),
    ("Uptime", "3 hours, 12 mins"),
    ("Packages", "1840 (pacman)"),
    ("Shell", "fish 4.7.1"),
    ("DE", "KDE Plasma 6.6"),
    ("WM", "KWin (Wayland)"),
    ("Terminal", "kitty"),
    ("CPU", "AMD Ryzen 7 7840HS"),
    ("GPU", "AMD Radeon 780M"),
    ("Memory", "6.2 GiB / 32 GiB"),
    ("Theme", "catppuccin-mocha"),
]


def run_fastfetch(binary):
    """Render fastfetch with the curated module set; return raw ANSI (with colors,
    cursor positioning intact). The title carries embedded SGR so it keeps the
    authentic two-tone bold look; the recolor pass normalizes it to the palette."""
    e = "\x1b"
    title = f"{e}[1m{e}[36m{TITLE_USER}{e}[39m@{e}[1m{e}[36m{TITLE_HOST}{e}[0m"
    rule = f"{e}[36m{'-' * (len(TITLE_USER) + 1 + len(TITLE_HOST))}{e}[0m"
    modules = [
        {"type": "custom", "format": title},
        {"type": "custom", "format": rule},
    ]
    modules += [{"type": "custom", "key": k, "format": v} for k, v in INFO]
    modules += ["break", {"type": "colors", "symbol": "block"}]
    cfg = {
        "logo": {"type": "builtin", "source": LOGO},
        "display": {"separator": ": "},
        "modules": modules,
    }
    proc = subprocess.run(
        [binary, "--config", "-", "--pipe", "false"],
        input=json.dumps(cfg).encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.exit(f"fastfetch failed: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace")


# --- Terminal grid emulation (flatten cursor positioning) ----------------------
TOKEN = re.compile(r"\x1b\[([0-9;]*)([A-Za-z])")


def emulate(raw):
    """Replay fastfetch's byte stream onto a sparse cell grid, honoring the SGR
    and cursor-move escapes it actually emits (m, A/B/C/D, G, H/f; CR/LF/TAB).
    Returns {(row, col): (char, fg, bg, bold)}, max_row, {row: max_col}."""
    grid = {}
    fg = bg = None
    bold = False
    row = col = max_row = 0
    max_col = {}
    pos = 0

    def put(ch):
        nonlocal col, max_row
        grid[(row, col)] = (ch, fg, bg, bold)
        max_col[row] = max(max_col.get(row, 0), col)
        max_row = max(max_row, row)
        col += 1

    def text(s):
        nonlocal row, col, max_row
        for ch in s:
            if ch == "\n":
                row += 1
                col = 0
                max_row = max(max_row, row)
            elif ch == "\r":
                col = 0
            elif ch == "\t":
                col += 8 - (col % 8)
            else:
                put(ch)

    for m in TOKEN.finditer(raw):
        text(raw[pos:m.start()])
        pos = m.end()
        params, final = m.group(1), m.group(2)
        if final == "m":
            nums = [int(p) if p else 0 for p in (params.split(";") if params else ["0"])]
            i = 0
            while i < len(nums):
                v = nums[i]
                if v == 0:
                    fg = bg = None
                    bold = False
                elif v == 1:
                    bold = True
                elif v == 22:
                    bold = False
                elif 30 <= v <= 37:
                    fg = ("i", v - 30)
                elif v == 39:
                    fg = None
                elif 90 <= v <= 97:
                    fg = ("i", v - 90 + 8)
                elif 40 <= v <= 47:
                    bg = ("i", v - 40)
                elif v == 49:
                    bg = None
                elif 100 <= v <= 107:
                    bg = ("i", v - 100 + 8)
                elif v in (38, 48) and i + 1 < len(nums) and nums[i + 1] == 2:
                    c = ("rgb", nums[i + 2], nums[i + 3], nums[i + 4])
                    fg, i = (c, i + 4) if v == 38 else (fg, i + 4)
                    if v == 48:
                        bg = c
                elif v in (38, 48) and i + 1 < len(nums) and nums[i + 1] == 5:
                    c = ("x", nums[i + 2])
                    if v == 38:
                        fg = c
                    else:
                        bg = c
                    i += 2
                i += 1
        elif final == "A":
            row = max(0, row - int(params or 1))
        elif final == "B":
            row += int(params or 1)
            max_row = max(max_row, row)
        elif final == "C":
            col += int(params or 1)
        elif final == "D":
            col = max(0, col - int(params or 1))
        elif final == "G":
            col = max(0, int(params or 1) - 1)
        elif final in "Hf":
            pp = (params or "").split(";")
            row = (int(pp[0]) if pp[0] else 1) - 1
            col = (int(pp[1]) if len(pp) > 1 and pp[1] else 1) - 1
            max_row = max(max_row, row)
        # other finals (J/K erase, etc.) are not emitted by fastfetch here -> ignore
    text(raw[pos:])
    return grid, max_row, max_col


# --- Recolor + serialize -------------------------------------------------------
def hex_of(color, default):
    if color is None:
        return default
    kind = color[0]
    if kind == "i":
        return PALETTE[color[1]]
    if kind == "rgb":
        return "#%02x%02x%02x" % (color[1], color[2], color[3])
    if kind == "x":  # xterm-256 -> rgb (logo here never uses it; kept for safety)
        n = color[1]
        if n < 16:
            return PALETTE[n]
        if n >= 232:
            g = 8 + (n - 232) * 10
            return "#%02x%02x%02x" % (g, g, g)
        n -= 16
        conv = lambda c: 0 if c == 0 else 55 + c * 40
        return "#%02x%02x%02x" % (conv(n // 36), conv((n % 36) // 6), conv(n % 6))
    return default


def _rgb(hx):
    hx = hx.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


def sgr(fg_hex, bg_hex, bold):
    out = "\x1b[0m"
    if bold:
        out += "\x1b[1m"
    r, g, b = _rgb(fg_hex)
    out += f"\x1b[38;2;{r};{g};{b}m"
    if bg_hex:
        r, g, b = _rgb(bg_hex)
        out += f"\x1b[48;2;{r};{g};{b}m"
    return out


def serialize(grid, max_row, max_col):
    """Emit the grid as truecolor ANSI lines (trailing blank cells trimmed; gaps
    between logo and info kept as spaces so the columns stay aligned)."""
    lines = []
    for row in range(max_row + 1):
        width = max_col.get(row, -1)
        cur = None
        buf = []
        for col in range(width + 1):
            ch, fg, bg, bold = grid.get((row, col), (" ", None, None, False))
            fg_hex = hex_of(fg, DEFAULT_FG)
            bg_hex = hex_of(bg, None) if bg else None
            state = (fg_hex, bg_hex, bold)
            if state != cur:
                buf.append(sgr(fg_hex, bg_hex, bold))
                cur = state
            buf.append(ch)
        buf.append("\x1b[0m")
        lines.append("".join(buf))
    return lines


# --- Shell prompt framing ------------------------------------------------------
def fg(hx):
    r, g, b = _rgb(hx)
    return f"\x1b[38;2;{r};{g};{b}m"


def prompt(trailing=False):
    r = "\x1b[0m"
    b = "\x1b[1m"
    tail = f"{fg(DEFAULT_FG)}█{r}" if trailing else f"{fg(DEFAULT_FG)}fastfetch{r}"
    return (
        f"{fg(P_USER)}{b}{TITLE_USER}{r}{fg(DEFAULT_FG)}@{fg(P_USER)}{b}{TITLE_HOST}{r} "
        f"{fg(P_PATH)}{b}~{r} {fg(P_GIT)}❯{r} {tail}"
    )


def main():
    binary = shutil.which("fastfetch")
    if not binary:
        sys.exit("fastfetch not found on PATH")
    grid, max_row, max_col = emulate(run_fastfetch(binary))
    body = serialize(grid, max_row, max_col)
    lines = [prompt(), ""] + body + ["", prompt(trailing=True)]
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
