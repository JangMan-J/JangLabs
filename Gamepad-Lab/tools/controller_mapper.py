"""controller_mapper.py -- guided HID discovery for 8BitDo Ultimate 2 DInput.

Two jobs:
  1. Walk the user through each physical control, requiring N clean press-release
     cycles on the same stable bit before accepting a mapping. No prior hypothesis
     from BUTTON_MAP -- rediscovered from scratch.
  2. Passively observe the full 34-byte packet throughout the session, categorize
     every byte's activity, and flag any unmapped bits that fired (possible
     firmware aliases).

At end of session, writes a timestamped markdown report to reference/ with:
  - A discovered BUTTON_MAP dict ready to paste into jsm_bridge.py
  - A DPAD_MAP showing the nibble value for each direction
  - A per-byte categorization of the whole HID report (Function 2)
  - Any unmapped bits that fired, attributed to whichever target was active

Usage:
  python tools/controller_mapper.py [--reps N]

Keys during discovery:
  R  retry current target   S  skip current target   Q  quit + write report
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

if os.name != "nt":
    sys.exit("controller_mapper.py is Windows-only (uses msvcrt for key input).")

import msvcrt

try:
    import hid
except ImportError:
    sys.exit("hidapi not found. Run: pip install hidapi")


# ── Config ────────────────────────────────────────────────────────────────────

VID, PID       = 0x2DC8, 0x6012
REPORT_LEN     = 34
DEFAULT_REPS   = 3
BASELINE_SECS  = 2.0
DPAD_HOLD_SECS = 0.25   # how long DPad must be held at a single value to accept
POLL_TIMEOUT   = 20      # ms

# Bytes where we trust stable-bit edges to mean "button press"
BUTTON_REGION_BYTES = set(range(8, 14)) | {1}

# Bytes known to be analog sensors / counters -- excluded from button-alias flagging
SENSOR_BYTES        = set(range(2, 8)) | set(range(14, 27))

# Report directory (reference/ at the workspace root)
REPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reference",
)


# ── Targets (Scope A: binary only -- 17 buttons + 8 DPad directions) ─────────

@dataclass
class Target:
    name: str
    kind: str   # "button" or "dpad"
    hint: str


TARGETS: list[Target] = [
    # Face buttons
    Target("B",      "button", "South face button"),
    Target("A",      "button", "East face button"),
    Target("X",      "button", "West face button"),
    Target("Y",      "button", "North face button"),
    # Shoulders + triggers (digital clicks)
    Target("L1",     "button", "Upper left shoulder"),
    Target("R1",     "button", "Upper right shoulder"),
    Target("L2d",    "button", "Left trigger at full pull (digital click)"),
    Target("R2d",    "button", "Right trigger at full pull (digital click)"),
    # System
    Target("Select", "button", "Select / Share / Minus"),
    Target("Start",  "button", "Start / Options / Plus"),
    Target("L3",     "button", "Left stick click-in"),
    Target("R3",     "button", "Right stick click-in"),
    Target("Home",   "button", "Home / Guide button"),
    # Extras (must have firmware aliases cleared in 8BitDo Ultimate Software)
    Target("L4",     "button", "Extra upper-left shoulder (above L1)"),
    Target("R4",     "button", "Extra upper-right shoulder (above R1)"),
    Target("PL",     "button", "Back paddle, left"),
    Target("PR",     "button", "Back paddle, right"),
    # DPad (hold each direction ~0.5s)
    Target("DPad_N",  "dpad", "DPad Up"),
    Target("DPad_NE", "dpad", "DPad Up + Right (diagonal -- press both)"),
    Target("DPad_E",  "dpad", "DPad Right"),
    Target("DPad_SE", "dpad", "DPad Down + Right (diagonal)"),
    Target("DPad_S",  "dpad", "DPad Down"),
    Target("DPad_SW", "dpad", "DPad Down + Left (diagonal)"),
    Target("DPad_W",  "dpad", "DPad Left"),
    Target("DPad_NW", "dpad", "DPad Up + Left (diagonal)"),
]


# ── Terminal / keyboard helpers ───────────────────────────────────────────────

def _enable_vt_mode() -> None:
    """Enable ANSI escape sequences on Windows cmd.exe (best-effort)."""
    try:
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def read_key() -> Optional[str]:
    """Return a lowercased single char if a key is waiting, else None."""
    if not msvcrt.kbhit():
        return None
    ch = msvcrt.getch()
    if ch in (b"\x00", b"\xe0"):       # function / arrow prefix -- consume second byte
        if msvcrt.kbhit():
            msvcrt.getch()
        return None
    try:
        return ch.decode("ascii", errors="ignore").lower()
    except Exception:
        return None


def drain_keys() -> None:
    """Consume any keys buffered before a prompt starts."""
    while msvcrt.kbhit():
        msvcrt.getch()


# ── HID device ────────────────────────────────────────────────────────────────

def open_device() -> hid.device:
    for info in hid.enumerate(VID, PID):
        dev = hid.device()
        dev.open_path(info["path"])
        return dev
    raise RuntimeError(
        f"8BitDo DInput device (VID={VID:#06x} PID={PID:#06x}) not found.\n"
        "Check:\n"
        "  * DInput mode active (hold B during power-on, LED blinks blue)\n"
        "  * 8BitDo Ultimate Software closed (right-click tray icon -> Exit)"
    )


# ── Observer (Function 2: passive full-packet tracking) ──────────────────────

class Observer:
    """Tracks all bits/bytes across the whole session.

    Changes during an active discovery prompt are attributed to that target
    so the report can surface firmware aliases ('bit X also flipped every
    time we were mapping [B]').
    """

    def __init__(self) -> None:
        self.bit_changes: dict[tuple[int, int], int]              = defaultdict(int)
        self.byte_range:  dict[int, tuple[int, int]]              = {}
        self.byte_last:   dict[int, int]                          = {}
        self.attributions: dict[tuple[int, int], dict[str, int]]  = defaultdict(lambda: defaultdict(int))
        self.byte_monotonic_hits:   dict[int, int]                = defaultdict(int)
        self.byte_monotonic_misses: dict[int, int]                = defaultdict(int)
        self.current_target: Optional[str] = None
        self.total_samples = 0
        self._prev: Optional[bytes] = None

    def set_target(self, name: Optional[str]) -> None:
        self.current_target = name

    def observe(self, packet: bytes) -> None:
        self.total_samples += 1

        for i in range(len(packet)):
            b = packet[i]
            lo, hi = self.byte_range.get(i, (b, b))
            self.byte_range[i] = (min(lo, b), max(hi, b))

            prev_b = self.byte_last.get(i)
            if prev_b is not None and b != prev_b:
                diff = (b - prev_b) & 0xFF
                if 0 < diff <= 4:
                    self.byte_monotonic_hits[i] += 1
                else:
                    self.byte_monotonic_misses[i] += 1
            self.byte_last[i] = b

        if self._prev is not None:
            for i in range(len(packet)):
                xor = packet[i] ^ self._prev[i]
                if xor:
                    for bit in range(8):
                        if xor & (1 << bit):
                            self.bit_changes[(i, bit)] += 1
                            if self.current_target:
                                self.attributions[(i, bit)][self.current_target] += 1
        self._prev = packet


# ── Baseline ──────────────────────────────────────────────────────────────────

def capture_baseline(dev: hid.device, observer: Observer, duration: float
                     ) -> tuple[bytes, set[tuple[int, int]]]:
    """Record idle state. Returns (reference_packet, stable_bits_in_button_region).

    A bit is 'stable' if it never changed during the baseline window -- those
    are the only bits we trust as press-edge signals.
    """
    print(f"[baseline] Keep hands off the controller for {duration:.0f}s...", flush=True)
    deadline = time.monotonic() + duration
    first: Optional[bytes] = None
    changed: set[tuple[int, int]] = set()

    while time.monotonic() < deadline:
        raw = bytes(dev.read(REPORT_LEN, timeout_ms=POLL_TIMEOUT))
        if not raw or len(raw) < REPORT_LEN or raw[0] != 0x01:
            continue
        observer.observe(raw)
        if first is None:
            first = raw
            continue
        for i in range(REPORT_LEN):
            xor = raw[i] ^ first[i]
            if xor:
                for bit in range(8):
                    if xor & (1 << bit):
                        changed.add((i, bit))

    if first is None:
        raise RuntimeError("Baseline: no packets received (controller disconnected?).")

    all_bits = {(i, bit) for i in range(REPORT_LEN) for bit in range(8)}
    stable   = all_bits - changed
    stable   = {(i, bit) for (i, bit) in stable if i in BUTTON_REGION_BYTES}

    print(f"[baseline] {len(stable)} stable bits in button region "
          f"(bytes {sorted(BUTTON_REGION_BYTES)}).", flush=True)
    return first, stable


# ── Discovery ────────────────────────────────────────────────────────────────

@dataclass
class DiscoveryResult:
    target: Target
    bit:        Optional[tuple[int, int]] = None    # (byte, bit_index) for buttons
    dpad_value: Optional[int]             = None    # nibble for DPad directions
    skipped:    bool                      = False
    notes:      list[str]                 = field(default_factory=list)


def _print_intro(index: int, total: int, target: Target, reps: int) -> None:
    print()
    print("-" * 64)
    print(f"[{index}/{total}] {target.name}  --  {target.hint}")
    if target.kind == "button":
        print(f"   Press and release {reps} times.")
    else:
        print(f"   Press and HOLD for ~0.5s, then release.")
    print(f"   Keys: [R]retry  [S]skip  [Q]quit-and-log")


def discover_button(
    dev:        hid.device,
    observer:   Observer,
    target:     Target,
    baseline:   bytes,
    stable:     set[tuple[int, int]],
    reps:       int,
) -> DiscoveryResult:
    """Require `reps` clean press-release cycles; accept a bit only if it
    fires in every cycle with no other bit consistently tied.
    """
    drain_keys()
    cycle_bits:        list[set[tuple[int, int]]] = []
    pressed_prev:      set[tuple[int, int]]       = set()
    cycle_seen:        set[tuple[int, int]]       = set()

    while len(cycle_bits) < reps:
        raw = bytes(dev.read(REPORT_LEN, timeout_ms=POLL_TIMEOUT))
        k = read_key()
        if k == "s":
            return DiscoveryResult(target, skipped=True, notes=["skipped by user"])
        if k == "q":
            raise KeyboardInterrupt
        if k == "r":
            print("   [retry] cycles reset.")
            cycle_bits.clear()
            cycle_seen.clear()
            pressed_prev.clear()
            continue
        if not raw or len(raw) < REPORT_LEN or raw[0] != 0x01:
            continue

        observer.observe(raw)

        # Which stable bits are currently != baseline?
        now_pressed = {
            (b, bit) for (b, bit) in stable
            if (raw[b] & (1 << bit)) != (baseline[b] & (1 << bit))
        }
        cycle_seen.update(now_pressed)

        # Detect return-to-baseline -> end of one cycle
        if pressed_prev and not now_pressed:
            if cycle_seen:
                cycle_bits.append(cycle_seen.copy())
                fired = ", ".join(f"byte{b}.bit{bit}(0x{1<<bit:02x})"
                                  for (b, bit) in sorted(cycle_seen))
                print(f"   cycle {len(cycle_bits)}/{reps}: {fired}")
            cycle_seen.clear()

        pressed_prev = now_pressed

    # All reps captured -- bits that fired in EVERY cycle are candidates
    consistent = set.intersection(*cycle_bits) if cycle_bits else set()

    if not consistent:
        return DiscoveryResult(
            target, skipped=True,
            notes=[f"no bit fired consistently across all {reps} cycles"],
        )

    if len(consistent) == 1:
        b, bit = next(iter(consistent))
        # Mention any bits that fired in some cycles but not all (transient noise)
        union = set.union(*cycle_bits)
        extras = sorted(union - consistent)
        notes = []
        if extras:
            notes.append("noisy co-firers (not every cycle): "
                         + ", ".join(f"byte{x}.bit{y}" for (x, y) in extras))
        return DiscoveryResult(target, bit=(b, bit), notes=notes)

    return _resolve_ambiguity(target, consistent, cycle_bits)


def _resolve_ambiguity(target: Target,
                       consistent: set[tuple[int, int]],
                       cycle_bits: list[set[tuple[int, int]]]) -> DiscoveryResult:
    """Pause and ask the user which bit is physical vs. firmware alias."""
    cands = sorted(consistent)
    print()
    print("   " + "=" * 56)
    print(f"   Ambiguity: {len(cands)} bits fired on every cycle for [{target.name}]:")
    for i, (b, bit) in enumerate(cands, start=1):
        print(f"     [{i}] byte{b} bit{bit}  (mask 0x{1 << bit:02x})")
    print("     [s] skip this target (treat as aliased / no physical bit)")
    print("   Which is the physical button?")
    print("   " + "=" * 56)
    while True:
        sys.stdout.write("   > ")
        sys.stdout.flush()
        ch = msvcrt.getch().decode("ascii", errors="ignore").lower()
        sys.stdout.write(ch + "\n")
        sys.stdout.flush()
        if ch == "s":
            return DiscoveryResult(
                target, skipped=True,
                notes=[f"ambiguous -- all of {cands} fired every cycle; user skipped"],
            )
        if ch.isdigit():
            idx = int(ch)
            if 1 <= idx <= len(cands):
                chosen = cands[idx - 1]
                others = [c for c in cands if c != chosen]
                notes = [f"aliased co-firers: "
                         + ", ".join(f"byte{b}.bit{bit}" for (b, bit) in others)]
                return DiscoveryResult(target, bit=chosen, notes=notes)


def discover_dpad(
    dev:      hid.device,
    observer: Observer,
    target:   Target,
    baseline: bytes,
) -> DiscoveryResult:
    """Wait for byte 1 low nibble to hold a non-baseline value for DPAD_HOLD_SECS."""
    drain_keys()
    baseline_nibble = baseline[1] & 0x0F
    held_value: Optional[int] = None
    held_since: Optional[float] = None

    while True:
        raw = bytes(dev.read(REPORT_LEN, timeout_ms=POLL_TIMEOUT))
        k = read_key()
        if k == "s":
            return DiscoveryResult(target, skipped=True, notes=["skipped by user"])
        if k == "q":
            raise KeyboardInterrupt
        if k == "r":
            print("   [retry] hold tracker reset.")
            held_value = None
            held_since = None
            continue
        if not raw or len(raw) < REPORT_LEN or raw[0] != 0x01:
            continue

        observer.observe(raw)

        nibble = raw[1] & 0x0F
        if nibble == baseline_nibble:
            held_value = None
            held_since = None
            continue

        if held_value is None or nibble != held_value:
            held_value = nibble
            held_since = time.monotonic()
            continue

        if time.monotonic() - held_since >= DPAD_HOLD_SECS:
            print(f"   held nibble = 0x{held_value:x} -- accepted")
            return DiscoveryResult(target, dpad_value=held_value)


# ── Runner ────────────────────────────────────────────────────────────────────

def run_mapper(reps: int) -> None:
    _enable_vt_mode()
    os.makedirs(REPORT_DIR, exist_ok=True)

    print("controller_mapper  --  8BitDo Ultimate 2 DInput HID discovery")
    print("=" * 64)
    print(f"Reps per button : {reps}")
    print(f"Targets         : {len(TARGETS)}")
    print(f"Log destination : {REPORT_DIR}\\")
    print("=" * 64)

    print("\n[open] Opening HID device...", flush=True)
    dev = open_device()
    print("[open] OK.")

    observer = Observer()
    baseline, stable_bits = capture_baseline(dev, observer, BASELINE_SECS)

    if not stable_bits:
        print("WARNING: no stable bits in button region -- baseline may be unreliable.")

    results: list[DiscoveryResult] = []
    aborted = False

    try:
        for idx, target in enumerate(TARGETS, start=1):
            _print_intro(idx, len(TARGETS), target, reps)
            observer.set_target(target.name)
            if target.kind == "button":
                result = discover_button(dev, observer, target, baseline, stable_bits, reps)
            else:
                result = discover_dpad(dev, observer, target, baseline)
            observer.set_target(None)

            if result.skipped:
                print(f"   SKIPPED: {'; '.join(result.notes) or '(no notes)'}")
            elif result.bit is not None:
                b, bit = result.bit
                print(f"   OK: byte{b} bit{bit}  (mask 0x{1 << bit:02x})")
                for note in result.notes:
                    print(f"       note: {note}")
            elif result.dpad_value is not None:
                print(f"   OK: byte1 nibble = 0x{result.dpad_value:x}")

            results.append(result)

    except KeyboardInterrupt:
        print("\n[quit] Quit requested -- writing partial report...")
        aborted = True

    observer.set_target(None)
    path = write_report(observer, results, baseline, stable_bits, reps, aborted)
    print(f"\n[report] Wrote: {path}")
    dev.close()


# ── Report generation ────────────────────────────────────────────────────────

def write_report(
    observer:   Observer,
    results:    list[DiscoveryResult],
    baseline:   bytes,
    stable:     set[tuple[int, int]],
    reps:       int,
    aborted:    bool,
) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path  = os.path.join(REPORT_DIR, f"controller_map_{stamp}.md")

    accepted_buttons = [r for r in results if r.target.kind == "button" and r.bit is not None]
    accepted_dpad    = [r for r in results if r.target.kind == "dpad"   and r.dpad_value is not None]
    skipped          = [r for r in results if r.skipped]

    # Bits claimed by the accepted map (mapped_bits) -- for Function 2 filtering
    mapped_bits: set[tuple[int, int]] = set()
    mapped_bytes: set[int] = set()
    for r in accepted_buttons:
        if r.bit:
            mapped_bits.add(r.bit)
            mapped_bytes.add(r.bit[0])
    if accepted_dpad:
        mapped_bytes.add(1)
        for bit in range(4):
            mapped_bits.add((1, bit))

    L: list[str] = []
    L.append(f"# Controller HID map -- {datetime.now():%Y-%m-%d %H:%M:%S}")
    L.append("")
    L.append(f"- Device: VID {VID:#06x} / PID {PID:#06x} (8BitDo Ultimate 2 DInput)")
    L.append(f"- Reps required per button: **{reps}**")
    L.append(f"- Total packets observed: {observer.total_samples}")
    L.append(f"- Baseline packet (hex): `{baseline.hex()}`")
    if aborted:
        L.append("")
        L.append("> **Session aborted with Q -- results below are partial.**")
    L.append("")

    # ─── Accepted button map ─────────────────────────────────────────────────
    L.append("## Discovered BUTTON_MAP")
    L.append("")
    L.append("Paste into `tools/jsm_bridge.py` (replace the existing `BUTTON_MAP`).")
    L.append("")
    L.append("```python")
    L.append("BUTTON_MAP = {")
    for r in accepted_buttons:
        b, bit = r.bit
        mask   = 1 << bit
        tail   = f"  # {'; '.join(r.notes)}" if r.notes else ""
        L.append(f'    "{r.target.name:<7}": ({b}, 0x{mask:02x}),{tail}')
    L.append("}")
    L.append("```")
    L.append("")

    # ─── Accepted DPad nibble map ────────────────────────────────────────────
    if accepted_dpad:
        L.append("## Discovered DPAD_MAP")
        L.append("")
        L.append(f"Byte 1 low nibble encodes direction. "
                 f"Idle nibble: `0x{baseline[1] & 0x0F:x}`")
        L.append("")
        L.append("```python")
        L.append("DPAD_MAP = {")
        for r in accepted_dpad:
            L.append(f'    "{r.target.name:<9}": 0x{r.dpad_value:x},')
        L.append("}")
        L.append("```")
        L.append("")

    # ─── Skipped / ambiguous ──────────────────────────────────────────────────
    if skipped:
        L.append("## Skipped / ambiguous targets")
        L.append("")
        for r in skipped:
            note = '; '.join(r.notes) or '(no notes)'
            L.append(f"- **{r.target.name}** ({r.target.hint}) -- {note}")
        L.append("")

    # ─── Function 2: per-byte categorization ──────────────────────────────────
    L.append("## Unmapped packet data (Function 2)")
    L.append("")
    L.append("### Per-byte summary")
    L.append("")
    L.append("| Byte | Range | Bit changes | Category |")
    L.append("|------|-------|-------------|----------|")
    for i in range(REPORT_LEN):
        lo, hi  = observer.byte_range.get(i, (0, 0))
        changes = sum(observer.bit_changes.get((i, b), 0) for b in range(8))
        cat     = _categorize_byte(i, lo, hi, changes, observer)
        if i in mapped_bytes:
            cat = f"**mapped** -- {cat}"
        L.append(f"| {i:2d} | 0x{lo:02x}-0x{hi:02x} | {changes} | {cat} |")
    L.append("")

    # ─── Unmapped active bits ─────────────────────────────────────────────────
    L.append("### Unmapped bits that fired (possible firmware aliases)")
    L.append("")
    L.append("Only bits in the button region (bytes 1, 8-13) are listed; sensor/")
    L.append("counter bytes are expected to fluctuate and are covered above.")
    L.append("")
    unmapped_fired = [
        ((i, bit), cnt) for ((i, bit), cnt) in observer.bit_changes.items()
        if (i, bit) not in mapped_bits
           and i in BUTTON_REGION_BYTES
           and cnt > 0
    ]
    unmapped_fired.sort(key=lambda x: -x[1])

    if not unmapped_fired:
        L.append("_None. All button-region bit activity was claimed by the map._")
    else:
        L.append("| byte.bit | transitions | attribution (top 3 targets) |")
        L.append("|----------|-------------|------------------------------|")
        for (i, bit), cnt in unmapped_fired:
            attrs = observer.attributions.get((i, bit), {})
            top   = sorted(attrs.items(), key=lambda kv: -kv[1])[:3]
            astr  = ", ".join(f"{name}:{hits}" for name, hits in top) or "(none during prompts)"
            L.append(f"| byte{i}.bit{bit} | {cnt} | {astr} |")
    L.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return os.path.abspath(path)


def _categorize_byte(i: int, lo: int, hi: int, changes: int, observer: Observer) -> str:
    if lo == hi:
        return f"constant 0x{lo:02x}"
    hits   = observer.byte_monotonic_hits.get(i, 0)
    misses = observer.byte_monotonic_misses.get(i, 0)
    if hits > 50 and hits > misses * 3:
        return f"monotonic ({hits}/{hits+misses}) -- suspected counter/timestamp"
    if i in (15, 16, 17, 18, 19, 20):
        return "suspected accel axis (int16 LE)"
    if i in (21, 22, 23, 24, 25, 26):
        return "suspected gyro axis (int16 LE)"
    if i in (2, 3, 4, 5):
        return "suspected stick axis"
    if i in (6, 7):
        return "suspected trigger analog"
    if hi - lo > 32 and observer.total_samples and changes > observer.total_samples * 0.3:
        return "continuous variation -- suspected sensor/noise"
    if changes == 0:
        return f"flat at 0x{lo:02x} (never changed)"
    return "discrete activity"


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Guided HID controller mapper (Scope A).")
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS,
                    help=f"Press-release cycles required per button (default: {DEFAULT_REPS})")
    args = ap.parse_args()

    try:
        run_mapper(args.reps)
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
