#!/usr/bin/env python3
"""
Steam Input — Inventory Test Tool
Tests click/drag accuracy and input event timing against a simulated inventory grid.

Requirements: pip install pygame
"""

import math
import pygame
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

# ── Layout ────────────────────────────────────────────────────────────────────
CELL      = 54          # grid cell pixel size
COLS      = 10
ROWS      = 8
PAD       = 16          # margin around grid

INV_W     = COLS * CELL + PAD * 2    # 556
INV_H     = ROWS * CELL + PAD * 2    # 448
LOG_W     = 420
STATUS_H  = 96                        # extended for parameter controls
LOG_TOP_H = 270                       # event log takes top portion of right panel
SUMMARY_H = INV_H - LOG_TOP_H        # summary strip takes remainder (~178px)
WIN_W     = INV_W + LOG_W            # 976
WIN_H     = INV_H + STATUS_H         # 544

# ── Timing thresholds (runtime-adjustable defaults) ───────────────────────────
GYRO_FREEZE_MS      = 80    # ms of no MOUSEMOTION → infer gyro frozen
DOUBLE_FIRE_MS      = 50    # two LMB_DOWN within this gap = double-fire
POST_CLICK_WINDOW   = 50    # ms after LMB_DOWN to watch for drift (default)
DRIFT_PIXEL_WARN    = 2     # px of displacement within window (default)
POST_CLICK_STEP     = 5     # ms increment for runtime control
DRIFT_STEP          = 1     # px increment for runtime control
MARKER_TTL          = 3.0   # seconds before click marker fades
TRAIL_LEN           = 50    # mouse trail point history
MAX_LOG             = 200
MAX_SUMMARY         = 80

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    'bg':         (28,  28,  30),
    'inv_bg':     (40,  40,  44),
    'grid':       (56,  56,  62),
    'item':       [(65, 108, 158), (108, 65, 148), (65, 148, 108),
                   (148, 108, 65), (148, 65,  65), (65, 128, 128),
                   (108, 128, 65)],
    'item_hl':    (205, 195,  75),
    'hit':        ( 65, 210,  65),
    'miss':       (210,  65,  65),
    'lmb_dn':     (210,  65,  65),
    'lmb_up':     ( 65, 210,  65),
    'text':       (205, 205, 210),
    'dim':        (110, 110, 118),
    'log_bg':     (20,  20,  23),
    'sep':        (46,  46,  52),
    'gyro_on':    ( 65, 210,  65),
    'gyro_off':   (210,  65,  65),
    'warn':       (215, 170,  40),
    'status_bg':  (22,  22,  25),
    'trail':      (180, 180,  60),
    'lmb_dn_iv':  ( 90, 190, 210),   # Δdown interval — cyan
    'lmb_up_iv':  (175, 130, 215),   # Δup interval   — violet
    'hold':       (215, 180,  70),   # hold duration  — gold
}

# ── Items: (col, row, w_cells, h_cells, label) ────────────────────────────────
ITEM_DEFS = [
    (0, 0, 3, 1, "Rifle"),
    (3, 0, 2, 1, "Pistol"),
    (5, 0, 2, 3, "Med Bag"),
    (7, 0, 1, 1, "Ammo"),
    (8, 0, 1, 1, "Ammo"),
    (9, 0, 1, 1, "Ammo"),
    (0, 1, 2, 2, "Backpack"),
    (2, 1, 1, 2, "Medkit"),
    (3, 1, 2, 1, "Mag x2"),
    (7, 1, 2, 2, "Data Drive"),
    (9, 1, 1, 1, "Chip"),
    (3, 2, 1, 1, "Key"),
    (4, 2, 1, 1, "Fuse"),
    (9, 2, 1, 1, "Patch"),
    (0, 3, 1, 1, "Nade"),
    (1, 3, 1, 1, "Nade"),
    (2, 3, 3, 2, "Chest Rig"),
    (5, 3, 4, 2, "Body Armor"),
    (9, 3, 1, 1, "Scope"),
]


@dataclass
class Item:
    col: int
    row: int
    w: int
    h: int
    label: str
    color_idx: int
    dragging: bool = False
    drag_off: Tuple[int, int] = (0, 0)  # pixel offset within item where click landed

    def rect(self) -> pygame.Rect:
        return pygame.Rect(PAD + self.col * CELL, PAD + self.row * CELL,
                           self.w * CELL, self.h * CELL)

    def cells(self) -> List[Tuple[int, int]]:
        return [(self.col + dc, self.row + dr)
                for dr in range(self.h) for dc in range(self.w)]


@dataclass
class PostClickWatch:
    """Tracks cursor displacement in the window immediately after LMB_DOWN."""
    start_x: int
    start_y: int
    start_t: float
    peak_drift: float = 0.0        # max pixel distance from click point
    first_move_ms: Optional[float] = None  # ms until first movement detected
    settled: bool = False          # True once window has elapsed


@dataclass
class ClickMarker:
    x: int
    y: int
    hit: bool
    item_name: Optional[str]
    born: float
    double_fire: bool = False
    drift_px: Optional[float] = None   # filled in after POST_CLICK_WINDOW elapses


@dataclass
class LogEntry:
    t: float
    kind: str          # LMB_DOWN | LMB_UP | POST_CLICK | NOTE
    x: int
    y: int
    hit: Optional[bool] = None
    item_name: Optional[str] = None
    flag: Optional[str] = None   # DOUBLE_FIRE | SPURIOUS_UP | DRIFT
    hold_ms: Optional[float] = None
    drift_px: Optional[float] = None
    first_move_ms: Optional[float] = None
    shift_held: bool = False


@dataclass
class SummaryEntry:
    """One row per completed LMB click cycle (DOWN + UP).

    Built incrementally: stashed as `App._pending` on LMB_DOWN, finalized
    and appended to `App.summary` on LMB_UP. Rows never appear before the
    UP arrives, so each row represents a fully observed cycle.
    """
    t: float                                # timestamp of the cycle's first LMB_DOWN
    shift_held: bool = False                # True iff shift was down at BOTH DOWN and UP
    double_fire: bool = False               # set if a second DOWN arrived before the UP
    prev_down_ms: Optional[float] = None    # ms between this DOWN and previous DOWN
    prev_up_ms:   Optional[float] = None    # ms between this UP   and previous UP
    hold_ms:      Optional[float] = None    # DOWN→UP duration


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Steam Input — Inventory Test  [R=Reset  S=Save Log  ESC=Quit]")
        self.clock = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("Consolas", 11)
        self.font_md = pygame.font.SysFont("Consolas", 13)
        self.font_lg = pygame.font.SysFont("Consolas", 14, bold=True)

        self.items: List[Item] = self._build_items()
        self.dragged: Optional[Item] = None
        self.drag_cursor: Tuple[int, int] = (0, 0)

        self.log: deque = deque(maxlen=MAX_LOG)
        self.markers: List[ClickMarker] = []
        self.trail: deque = deque(maxlen=TRAIL_LEN)

        self.lmb_held        = False
        self.lmb_down_t: Optional[float] = None
        self.lmb_up_t: Optional[float]   = None
        self.last_move_t     = time.perf_counter()
        self.session_t       = time.perf_counter()
        self.clicks_this_hold = 0
        self.scroll          = 0

        # Post-click drift tracking
        self.post_click: Optional[PostClickWatch] = None
        self.last_marker: Optional[ClickMarker]   = None

        # Runtime-adjustable thresholds
        self.pw_ms  = POST_CLICK_WINDOW
        self.dw_px  = float(DRIFT_PIXEL_WARN)

        # Summary log
        self.summary: deque = deque(maxlen=MAX_SUMMARY)
        self.last_summary: Optional[SummaryEntry] = None
        # In-flight click cycle: created on LMB_DOWN, finalized on LMB_UP
        self._pending: Optional[SummaryEntry] = None

        # Hold duration history for rolling average
        self.hold_durations: deque = deque(maxlen=50)

        # All LMB event timestamps (both down and up) for interval average
        self.lmb_event_times: deque = deque(maxlen=200)

        # Button rects for threshold controls (populated in draw_status)
        self.btn_pw_minus = pygame.Rect(0, 0, 1, 1)
        self.btn_pw_plus  = pygame.Rect(0, 0, 1, 1)
        self.btn_dw_minus = pygame.Rect(0, 0, 1, 1)
        self.btn_dw_plus  = pygame.Rect(0, 0, 1, 1)

    # ── Item setup ────────────────────────────────────────────────────────────

    def _build_items(self) -> List[Item]:
        return [Item(c, r, w, h, lbl, i % len(C['item']))
                for i, (c, r, w, h, lbl) in enumerate(ITEM_DEFS)]

    def _reset(self):
        self.items = self._build_items()
        self.dragged = None
        self.log.clear()
        self.markers.clear()
        self.trail.clear()
        self.summary.clear()
        self.last_summary = None
        self._pending = None
        self.hold_durations.clear()
        self.lmb_event_times.clear()
        self.lmb_held = False
        self.lmb_down_t = None
        self.lmb_up_t = None
        self.clicks_this_hold = 0
        self.scroll = 0
        self.session_t = time.perf_counter()

    # ── Grid helpers ──────────────────────────────────────────────────────────

    def item_at(self, px: int, py: int) -> Optional[Item]:
        for item in self.items:
            if item.dragging:
                continue
            if item.rect().collidepoint(px, py):
                return item
        return None

    def grid_pos(self, px: int, py: int) -> Tuple[int, int]:
        return (px - PAD) // CELL, (py - PAD) // CELL

    def can_place(self, item: Item, col: int, row: int) -> bool:
        if col < 0 or row < 0 or col + item.w > COLS or row + item.h > ROWS:
            return False
        occupied = {cell for it in self.items if it is not item for cell in it.cells()}
        return all((col + dc, row + dr) not in occupied
                   for dc in range(item.w) for dr in range(item.h))

    # ── Input events ──────────────────────────────────────────────────────────

    def on_lmb_down(self, px: int, py: int):
        now   = time.perf_counter()
        flag  = None
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        self.lmb_event_times.append(now)

        if self.lmb_held:
            # LMB fired again without an up — double-fire; extend the in-flight cycle
            flag = "DOUBLE_FIRE"
            self.clicks_this_hold += 1
            if self._pending is not None:
                self._pending.double_fire = True
            if self.markers:
                self.markers[-1].double_fire = True
        else:
            self.clicks_this_hold = 1
            # Check rapid re-press (up was very recent)
            if self.lmb_up_t is not None and (now - self.lmb_up_t) * 1000 < DOUBLE_FIRE_MS:
                flag = "RAPID_REFIRE"
            # Open a new click cycle. lmb_down_t stays the FIRST DOWN of the cycle so
            # `hold_ms` and the live status-bar hold display reflect the full hold.
            prev_down_t = self.lmb_down_t   # captured before overwrite
            self.lmb_held   = True
            self.lmb_down_t = now
            self._pending = SummaryEntry(
                t            = now,
                shift_held   = shift,   # provisional; AND with shift state on UP
                prev_down_ms = (now - prev_down_t) * 1000 if prev_down_t is not None else None,
            )

        # Hit test (inventory area only)
        hit, item_name = False, None
        if 0 <= px < INV_W and 0 <= py < INV_H:
            item = self.item_at(px, py)
            if item is not None:
                hit = True
                item_name = item.label
                if shift:
                    # Quick move: snatch item from grid
                    self.items.remove(item)
                else:
                    ir = item.rect()
                    item.drag_off  = (px - ir.x, py - ir.y)
                    item.dragging  = True
                    self.dragged   = item
            self.drag_cursor = (px, py)

        self.log.append(LogEntry(now, "LMB_DOWN", px, py, hit, item_name, flag,
                                  shift_held=shift))

        # Click marker only on the first DOWN of a cycle (double-fire just flags existing)
        if flag != "DOUBLE_FIRE":
            marker = ClickMarker(px, py, hit, item_name, now)
            self.markers.append(marker)
            self.last_marker = marker

        # Start post-click drift watch
        self.post_click = PostClickWatch(start_x=px, start_y=py, start_t=now)

    def on_lmb_up(self, px: int, py: int):
        now   = time.perf_counter()
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        self.lmb_event_times.append(now)
        flag = None if self.lmb_held else "SPURIOUS_UP"
        hold_ms = (now - self.lmb_down_t) * 1000 if self.lmb_down_t else None
        prev_up_t = self.lmb_up_t   # captured before overwrite

        self.lmb_held = False
        self.lmb_up_t = now

        if hold_ms is not None:
            self.hold_durations.append(hold_ms)

        # Finalize the in-flight click cycle (no entry on SPURIOUS_UP — there was no DOWN)
        if self._pending is not None:
            se = self._pending
            se.hold_ms    = hold_ms
            se.prev_up_ms = (now - prev_up_t) * 1000 if prev_up_t is not None else None
            se.shift_held = se.shift_held and shift
            self.summary.append(se)
            self.last_summary = se
            self._pending = None

        self.log.append(LogEntry(now, "LMB_UP", px, py, flag=flag, hold_ms=hold_ms))

        # Drop
        if self.dragged is not None:
            item = self.dragged
            anchor_x = px - item.drag_off[0] + CELL // 2
            anchor_y = py - item.drag_off[1] + CELL // 2
            col, row = self.grid_pos(anchor_x, anchor_y)
            if self.can_place(item, col, row):
                item.col, item.row = col, row
            item.dragging = False
            self.dragged  = None

    def on_move(self, px: int, py: int):
        now = time.perf_counter()
        self.last_move_t = now
        self.trail.append((px, py, now))
        if self.dragged is not None:
            self.drag_cursor = (px, py)

        # Feed post-click drift watch while window is open
        if self.post_click is not None and not self.post_click.settled:
            elapsed_ms = (now - self.post_click.start_t) * 1000
            if elapsed_ms <= self.pw_ms:
                dx = px - self.post_click.start_x
                dy = py - self.post_click.start_y
                dist = math.hypot(dx, dy)
                if dist > 0 and self.post_click.first_move_ms is None:
                    self.post_click.first_move_ms = elapsed_ms
                self.post_click.peak_drift = max(self.post_click.peak_drift, dist)
    def tick_post_click(self):
        """Called each frame; settles the post-click watch once the window elapses."""
        if self.post_click is None or self.post_click.settled:
            return
        now = time.perf_counter()
        elapsed_ms = (now - self.post_click.start_t) * 1000
        if elapsed_ms < self.pw_ms:
            return

        w = self.post_click
        w.settled = True

        drifted = w.peak_drift >= self.dw_px
        flag    = "DRIFT" if drifted else None

        entry = LogEntry(
            t             = now,
            kind          = "POST_CLICK",
            x             = w.start_x,
            y             = w.start_y,
            flag          = flag,
            drift_px      = w.peak_drift,
            first_move_ms = w.first_move_ms,
        )
        self.log.append(entry)

        # Push drift result into the click marker
        if self.last_marker is not None:
            self.last_marker.drift_px = w.peak_drift

    # ── Gyro inference ────────────────────────────────────────────────────────

    def gyro_state(self) -> Tuple[str, tuple]:
        ms = (time.perf_counter() - self.last_move_t) * 1000
        return ("FROZEN", C['gyro_off']) if ms > GYRO_FREEZE_MS else ("ACTIVE", C['gyro_on'])

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw_inventory(self):
        s   = self.screen
        now = time.perf_counter()
        mx, my = pygame.mouse.get_pos()

        pygame.draw.rect(s, C['inv_bg'], (0, 0, INV_W, INV_H))

        # Grid lines
        for c in range(COLS + 1):
            x = PAD + c * CELL
            pygame.draw.line(s, C['grid'], (x, PAD), (x, PAD + ROWS * CELL))
        for r in range(ROWS + 1):
            y = PAD + r * CELL
            pygame.draw.line(s, C['grid'], (PAD, y), (PAD + COLS * CELL, y))

        # Items (non-dragged)
        for item in self.items:
            if item.dragging:
                continue
            r     = item.rect()
            hov   = r.collidepoint(mx, my)
            color = C['item_hl'] if hov else C['item'][item.color_idx]
            inner = r.inflate(-4, -4)
            pygame.draw.rect(s, color, inner, border_radius=3)
            lbl = self.font_sm.render(item.label, True, (18, 18, 18))
            s.blit(lbl, (inner.x + 3, inner.y + inner.h // 2 - lbl.get_height() // 2))

        # Dragged item: ghost at drop target + floating copy at cursor
        if self.dragged is not None:
            item = self.dragged
            anchor_x = self.drag_cursor[0] - item.drag_off[0] + CELL // 2
            anchor_y = self.drag_cursor[1] - item.drag_off[1] + CELL // 2
            col, row = self.grid_pos(anchor_x, anchor_y)
            valid    = self.can_place(item, col, row)
            g_color  = C['hit'] if valid else C['miss']

            # Ghost outline at potential drop position
            gx = PAD + col * CELL
            gy = PAD + row * CELL
            pygame.draw.rect(s, g_color,
                             pygame.Rect(gx + 2, gy + 2,
                                         item.w * CELL - 4, item.h * CELL - 4),
                             2, border_radius=3)

            # Floating copy following cursor
            fx = self.drag_cursor[0] - item.drag_off[0]
            fy = self.drag_cursor[1] - item.drag_off[1]
            fr = pygame.Rect(fx + 2, fy + 2, item.w * CELL - 4, item.h * CELL - 4)
            pygame.draw.rect(s, C['item'][item.color_idx], fr, border_radius=3)
            lbl = self.font_sm.render(item.label, True, (18, 18, 18))
            s.blit(lbl, (fr.x + 3, fr.y + fr.h // 2 - lbl.get_height() // 2))

        # Mouse trail
        trail = list(self.trail)
        for i, (tx, ty, tt) in enumerate(trail):
            age = now - tt
            if age > 0.5:
                continue
            alpha  = 1.0 - age / 0.5
            radius = max(1, int(3 * alpha))
            v      = int(160 * alpha)
            pygame.draw.circle(s, (v, v, 40), (tx, ty), radius)

        # Click markers
        for m in self.markers:
            age = now - m.born
            if age > MARKER_TTL:
                continue
            a     = max(0.0, 1.0 - age / MARKER_TTL)
            base  = C['hit'] if m.hit else C['miss']
            color = tuple(int(v * a) for v in base)
            sz    = 9
            pygame.draw.line(s, color, (m.x - sz, m.y), (m.x + sz, m.y), 2)
            pygame.draw.line(s, color, (m.x, m.y - sz), (m.x, m.y + sz), 2)
            pygame.draw.circle(s, color, (m.x, m.y), sz, 1)
            label_parts = []
            if m.double_fire:
                label_parts.append("×2!")
            if m.item_name:
                label_parts.append(m.item_name)
            if m.drift_px is not None:
                drift_color = C['warn'] if m.drift_px >= DRIFT_PIXEL_WARN else C['hit']
                drift_lbl = self.font_sm.render(f"{m.drift_px:.1f}px drift", True, drift_color)
                s.blit(drift_lbl, (m.x + sz + 2, m.y + 6))
            if label_parts:
                lbl_color = C['warn'] if m.double_fire else color
                lbl = self.font_sm.render("  ".join(label_parts), True, lbl_color)
                s.blit(lbl, (m.x + sz + 2, m.y - 7))

    def draw_log(self):
        s  = self.screen
        lx = INV_W
        pygame.draw.rect(s, C['log_bg'], (lx, 0, LOG_W, LOG_TOP_H))
        pygame.draw.line(s, C['sep'], (lx, 0), (lx, LOG_TOP_H))

        hdr = self.font_md.render("INPUT EVENT LOG", True, C['dim'])
        s.blit(hdr, (lx + 8, 7))
        pygame.draw.line(s, C['sep'], (lx, 24), (lx + LOG_W, 24))

        entries = list(self.log)
        t0      = self.session_t
        visible_end   = max(len(entries), 0)
        visible_start = max(0, visible_end - 28 - self.scroll)
        visible       = entries[visible_start:visible_end - self.scroll if self.scroll else visible_end]

        y      = 30
        line_h = 15
        for entry in reversed(visible):
            if y > LOG_TOP_H - 6:
                break

            rel_ms = (entry.t - t0) * 1000

            if entry.kind == "LMB_DOWN":
                color  = C['lmb_dn']
                prefix = "▼ LMB_DOWN"
            elif entry.kind == "LMB_UP":
                color  = C['lmb_up']
                prefix = "▲ LMB_UP  "
            elif entry.kind == "POST_CLICK":
                color  = C['warn'] if entry.flag == "DRIFT" else C['dim']
                prefix = "  DRIFT   "
            else:
                color  = C['dim']
                prefix = "  NOTE    "

            line = f"{rel_ms:9.2f}ms  {prefix}  ({entry.x:4d},{entry.y:4d})"

            if entry.kind == "POST_CLICK":
                line += f"  peak {entry.drift_px:.1f}px"
                if entry.first_move_ms is not None:
                    line += f"  first move @{entry.first_move_ms:.1f}ms"
                else:
                    line += "  no movement"
            elif entry.hit is True:
                line += f"  HIT [{entry.item_name}]"
                if entry.shift_held:
                    line += "  [SHIFT-GRAB]"
            elif entry.hit is False:
                line += "  MISS"
                if entry.shift_held:
                    line += "  [SHIFT]"
            if entry.hold_ms is not None:
                line += f"  held {entry.hold_ms:.0f}ms"

            s.blit(self.font_sm.render(line, True, color), (lx + 5, y))
            y += line_h

            if entry.flag:
                flag_color = C['warn'] if entry.flag != "SPURIOUS_UP" else C['miss']
                s.blit(self.font_sm.render(f"    ⚠  {entry.flag}", True, flag_color),
                       (lx + 5, y))
                y += line_h

        # Scroll hint
        if self.scroll:
            hint = self.font_sm.render(f"▲ scrolled back {self.scroll} entries", True, C['warn'])
            s.blit(hint, (lx + 5, LOG_TOP_H - 16))

    def draw_summary(self):
        """One row per LMB click cycle: Δdown / Δup / hold / shift (color-coded)."""
        s   = self.screen
        lx  = INV_W
        ty  = LOG_TOP_H
        pygame.draw.rect(s, C['status_bg'], (lx, ty, LOG_W, SUMMARY_H))
        pygame.draw.line(s, C['sep'], (lx, ty),         (lx + LOG_W, ty))
        pygame.draw.line(s, C['sep'], (lx, ty),         (lx, ty + SUMMARY_H))
        pygame.draw.line(s, C['sep'], (lx, ty + SUMMARY_H - 1), (lx + LOG_W, ty + SUMMARY_H - 1))

        hdr = self.font_md.render("CLICK SUMMARY", True, C['dim'])
        s.blit(hdr, (lx + 8, ty + 5))

        # Column x-offsets (relative to panel left edge)
        col_t     = lx + 6
        col_dn    = lx + 88
        col_up    = lx + 168
        col_hold  = lx + 244
        col_shift = lx + 322

        # Column headers, each in its column's own color
        y_hdr = ty + 20
        s.blit(self.font_sm.render("t",     True, C['dim']),       (col_t,     y_hdr))
        s.blit(self.font_sm.render("Δdown", True, C['lmb_dn_iv']), (col_dn,    y_hdr))
        s.blit(self.font_sm.render("Δup",   True, C['lmb_up_iv']), (col_up,    y_hdr))
        s.blit(self.font_sm.render("hold",  True, C['hold']),      (col_hold,  y_hdr))
        s.blit(self.font_sm.render("shift", True, C['dim']),       (col_shift, y_hdr))
        pygame.draw.line(s, C['sep'], (lx, ty + 33), (lx + LOG_W, ty + 33))

        entries = list(self.summary)
        y       = ty + SUMMARY_H - 4
        line_h  = 15
        t0      = self.session_t

        for se in reversed(entries):
            if y < ty + 36:
                break
            row_y = y - line_h

            # Timestamp
            rel_ms = (se.t - t0) * 1000
            s.blit(self.font_sm.render(f"{rel_ms:7.0f}ms", True, C['dim']),
                   (col_t, row_y))

            # Δdown
            if se.prev_down_ms is not None:
                s.blit(self.font_sm.render(f"{se.prev_down_ms:6.0f}ms",
                                           True, C['lmb_dn_iv']),
                       (col_dn, row_y))
            else:
                s.blit(self.font_sm.render("     —  ", True, C['dim']),
                       (col_dn, row_y))

            # Δup
            if se.prev_up_ms is not None:
                s.blit(self.font_sm.render(f"{se.prev_up_ms:5.0f}ms",
                                           True, C['lmb_up_iv']),
                       (col_up, row_y))
            else:
                s.blit(self.font_sm.render("    —  ", True, C['dim']),
                       (col_up, row_y))

            # Hold (always populated: rows only appear once the cycle completes on UP)
            if se.hold_ms is not None:
                s.blit(self.font_sm.render(f"{se.hold_ms:5.0f}ms",
                                           True, C['hold']),
                       (col_hold, row_y))
            else:
                s.blit(self.font_sm.render("    —  ", True, C['dim']),
                       (col_hold, row_y))

            # Shift indicator
            shift_color = C['item_hl'] if se.shift_held else C['dim']
            shift_mark  = "●" if se.shift_held else "·"
            s.blit(self.font_sm.render(shift_mark, True, shift_color),
                   (col_shift, row_y))

            # Double-fire marker (optional trailing badge)
            if se.double_fire:
                s.blit(self.font_sm.render("×2", True, C['warn']),
                       (col_shift + 24, row_y))

            y -= line_h

    def _draw_btn(self, s, label: str, rect: pygame.Rect, active: bool = False):
        """Draw a small clickable button, return the rect."""
        col = C['item_hl'] if active else C['sep']
        pygame.draw.rect(s, col, rect, border_radius=2)
        pygame.draw.rect(s, C['dim'], rect, 1, border_radius=2)
        txt = self.font_sm.render(label, True, C['text'])
        s.blit(txt, (rect.x + rect.w // 2 - txt.get_width() // 2,
                     rect.y + rect.h // 2 - txt.get_height() // 2))

    def draw_status(self):
        s  = self.screen
        sy = INV_H
        pygame.draw.rect(s, C['status_bg'], (0, sy, WIN_W, STATUS_H))
        pygame.draw.line(s, C['sep'], (0, sy), (WIN_W, sy))

        now        = time.perf_counter()
        mx, my     = pygame.mouse.get_pos()
        gyro_s, gc = self.gyro_state()
        lmb_s      = "DOWN" if self.lmb_held else "UP  "
        lmb_c      = C['lmb_dn'] if self.lmb_held else C['lmb_up']
        ms_still   = (now - self.last_move_t) * 1000
        shift_now  = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        shift_s    = "HELD" if shift_now else "    "
        shift_c    = C['item_hl'] if shift_now else C['dim']

        # Row 1 — live state
        y1 = sy + 8
        cols_r1 = [
            ("CURSOR",  f"{mx:4d}, {my:4d}",   C['text'],  8,   70),
            ("LMB",     lmb_s,                  lmb_c,     185,  222),
            ("GYRO",    gyro_s,                 gc,        310,  355),
            ("STILL",   f"{ms_still:6.1f}ms",  C['dim'],  460,  510),
            ("SHIFT",   shift_s,               shift_c,   620,  668),
        ]
        for label, val, vc, lx, vx in cols_r1:
            s.blit(self.font_md.render(label, True, C['dim']), (lx, y1))
            s.blit(self.font_lg.render(val,   True, vc),       (vx, y1 - 1))

        # Row 2 — hold / double-fire warnings + rolling avg hold
        y2 = sy + 30
        if self.lmb_held and self.lmb_down_t:
            hold_ms = (now - self.lmb_down_t) * 1000
            s.blit(self.font_md.render(f"Hold: {hold_ms:.0f}ms", True, C['warn']), (8, y2))
        if self.clicks_this_hold > 1:
            warn = self.font_lg.render(f"⚠  {self.clicks_this_hold}× LMB_DOWN this hold — DOUBLE FIRE", True, C['warn'])
            s.blit(warn, (185, y2 - 1))
        if len(self.lmb_event_times) >= 2:
            times     = list(self.lmb_event_times)
            intervals = [(times[i + 1] - times[i]) * 1000 for i in range(len(times) - 1)]
            avg_iv    = sum(intervals) / len(intervals)
            n         = len(intervals)
            s.blit(self.font_md.render("LMB INTERVAL", True, C['dim']),  (580, y2))
            s.blit(self.font_lg.render(f"{avg_iv:.0f}ms  n={n}", True, C['text']), (700, y2 - 1))

        # Row 3 — runtime threshold controls
        y3 = sy + 54
        BH, BW = 18, 20   # button height / width

        # POST_CLICK_WINDOW control
        s.blit(self.font_md.render("POST-CLICK WINDOW", True, C['dim']), (8, y3 + 1))
        val_str = self.font_lg.render(f"{self.pw_ms}ms", True, C['text'])
        s.blit(val_str, (178, y3))
        self.btn_pw_minus = pygame.Rect(222, y3, BW, BH)
        self.btn_pw_plus  = pygame.Rect(245, y3, BW, BH)
        self._draw_btn(s, "−", self.btn_pw_minus)
        self._draw_btn(s, "+", self.btn_pw_plus)

        # DRIFT_WARN control
        s.blit(self.font_md.render("DRIFT WARN", True, C['dim']), (290, y3 + 1))
        val_str2 = self.font_lg.render(f"{self.dw_px:.0f}px", True, C['text'])
        s.blit(val_str2, (384, y3))
        self.btn_dw_minus = pygame.Rect(414, y3, BW, BH)
        self.btn_dw_plus  = pygame.Rect(437, y3, BW, BH)
        self._draw_btn(s, "−", self.btn_dw_minus)
        self._draw_btn(s, "+", self.btn_dw_plus)

        # Row 4 — help strip
        y4 = sy + STATUS_H - 13
        help_txt = "R = reset    S = save log    ↑↓ = scroll log    ESC = quit    click [−][+] to tune thresholds"
        s.blit(self.font_sm.render(help_txt, True, C['dim']), (8, y4))

    # ── Log export ────────────────────────────────────────────────────────────

    def save_log(self):
        t0   = self.session_t
        path = f"input_log_{int(time.time())}.txt"
        with open(path, "w") as f:
            f.write("Steam Input Inventory Test — Event Log\n")
            f.write(f"Session start: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"{'rel_ms':>10}  {'kind':<12}  {'x':>5} {'y':>5}  {'detail'}\n")
            f.write("-" * 72 + "\n")
            for e in self.log:
                rel = (e.t - t0) * 1000
                detail = ""
                if e.kind == "POST_CLICK":
                    detail += f"peak_drift={e.drift_px:.1f}px"
                    if e.first_move_ms is not None:
                        detail += f"  first_move={e.first_move_ms:.1f}ms"
                    else:
                        detail += "  no_movement"
                else:
                    if e.shift_held:
                        detail += "SHIFT  "
                    if e.hit is True:
                        detail += f"HIT [{e.item_name}]  "
                    elif e.hit is False:
                        detail += "MISS  "
                    if e.hold_ms is not None:
                        detail += f"held {e.hold_ms:.1f}ms  "
                if e.flag:
                    detail += f"*** {e.flag} ***"
                f.write(f"{rel:10.2f}  {e.kind:<12}  {e.x:>5} {e.y:>5}  {detail}\n")
        print(f"Log saved: {path}")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                    elif event.key == pygame.K_r:
                        self._reset()
                    elif event.key == pygame.K_s:
                        self.save_log()
                    elif event.key == pygame.K_UP:
                        self.scroll = min(self.scroll + 1, max(0, len(self.log) - 5))
                    elif event.key == pygame.K_DOWN:
                        self.scroll = max(self.scroll - 1, 0)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    px, py = event.pos
                    # Check threshold control buttons first
                    if self.btn_pw_minus.collidepoint(px, py):
                        self.pw_ms = max(10, self.pw_ms - POST_CLICK_STEP)
                    elif self.btn_pw_plus.collidepoint(px, py):
                        self.pw_ms = min(500, self.pw_ms + POST_CLICK_STEP)
                    elif self.btn_dw_minus.collidepoint(px, py):
                        self.dw_px = max(1, self.dw_px - DRIFT_STEP)
                    elif self.btn_dw_plus.collidepoint(px, py):
                        self.dw_px = min(50, self.dw_px + DRIFT_STEP)
                    else:
                        self.on_lmb_down(px, py)

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.on_lmb_up(*event.pos)

                elif event.type == pygame.MOUSEMOTION:
                    self.on_move(*event.pos)

            # Settle post-click drift watch
            self.tick_post_click()

            # Expire old markers
            now = time.perf_counter()
            self.markers = [m for m in self.markers if now - m.born < MARKER_TTL]

            self.screen.fill(C['bg'])
            self.draw_inventory()
            self.draw_log()
            self.draw_summary()
            self.draw_status()
            pygame.display.flip()
            self.clock.tick(120)


if __name__ == "__main__":
    app = App()
    app.run()
