# ============================================================================
# DEPRECATED as of 2026-04-20 — superseded by the direct JSM + SDL3 path.
#
# JSM master with its default SDL3 backend reaches this pad natively via
# SDL3's SDL_hidapi_8bitdo driver (verified Phase 2 live, matching Branch B —
# 13/13 standard buttons + gyro full-scale; paddles unreachable at JSM layer
# but the DS4 report format this bridge produces also cannot surface them,
# so it is bridge parity). The Python + virtual-DS4 hop is no longer needed.
#
# See findings/jsm_sdl3_verified.md for adoption details and the JSM config
# scaffold at tools/jsm_sdl3_config.txt. This file is kept as fallback
# reference in case a regression surfaces — do not delete without updating
# the finding.
# ============================================================================

"""jsm_bridge.py -- 8BitDo Ultimate 2 DInput -> virtual DS4 bridge for JoyShockMapper.

Reads raw HID from the 8BitDo in DInput mode (VID 0x2DC8 / PID 0x6012),
translates every report into a 63-byte DS4 HID report, and feeds it into a
ViGEm virtual DualShock 4. JoyShockMapper sees the virtual DS4 as a real
controller with full-range gyro (no NS-mode cap).

Prerequisites:
  pip install hidapi
  ViGEm Bus driver: https://github.com/nefarius/ViGEmBus/releases
  ViGEmClient.dll — auto-discovered from System32, ViGEm install dir,
                    or vgamepad package (pip install vgamepad).

Usage:
  python tools/jsm_bridge.py

Before running:
  1. Power on controller in DInput mode (hold B during power-on).
  2. Close 8BitDo Ultimate Software if running (right-click tray → Exit).
  3. Run this script, then open JoyShockMapper and press F1 to connect.

HID layout source of truth: reference/controller_map_<stamp>.md produced
by tools/controller_mapper.py. Regenerate that if the device firmware or
in-app remapping changes; then resync BUTTON_MAP / EXTRA_BUTTONS below.
"""

import ctypes
import os
import signal
import struct
import sys
import time

try:
    import hid
except ImportError:
    sys.exit("hidapi not found. Run: pip install hidapi")

# ── Configuration ─────────────────────────────────────────────────────────────

VID, PID   = 0x2DC8, 0x6012
REPORT_LEN = 34

GYRO_SCALE    = 2000.0 / 32767.0   # °/s per LSB — same on DS4, so raw pass-through
POLL_INTERVAL = 0.008               # 8 ms → 125 Hz ceiling, matching controller rate

# Override if DLL is not auto-discovered (set full path as a string).
VIGEM_DLL_PATH = None

# ── Button mapping ─────────────────────────────────────────────────────────────
# Format: (byte_index_in_raw_report, bit_mask)
#
# Buttons mapped onto the virtual DS4 report (reachable from JoyShockMapper).
# Face-button position mapping follows the 8BitDo physical layout:
#   North=Y, East=A, South=B, West=X  ->  Triangle, Circle, Cross, Square.
#
# Verified 2026-04-19 by tools/controller_mapper.py (3-rep guided discovery,
# 52,697 packets, 0 unmapped button-region bits fired).  See report in
# reference/controller_map_*.md.
BUTTON_MAP = {
    "B":      (8,  0x02),  # South  -> Cross    (DS4 byte4 bit5)
    "A":      (8,  0x01),  # East   -> Circle   (DS4 byte4 bit6)
    "X":      (8,  0x08),  # West   -> Square   (DS4 byte4 bit4)
    "Y":      (8,  0x10),  # North  -> Triangle (DS4 byte4 bit7)
    "L1":     (8,  0x40),  # L1                 (DS4 byte5 bit0)
    "R1":     (8,  0x80),  # R1                 (DS4 byte5 bit1)
    "L2d":    (9,  0x01),  # L2 digital         (DS4 byte5 bit2)
    "R2d":    (9,  0x02),  # R2 digital         (DS4 byte5 bit3)
    "Select": (9,  0x04),  # Share              (DS4 byte5 bit4)
    "Start":  (9,  0x08),  # Options            (DS4 byte5 bit5)
    "L3":     (9,  0x20),  # L3                 (DS4 byte5 bit6)
    "R3":     (9,  0x40),  # R3                 (DS4 byte5 bit7)
    "Home":   (9,  0x10),  # PS button          (DS4 byte6 bit0)
}

# Extra 8BitDo buttons with NO DS4 slot under ViGEm emulation.
# These come in two symmetric pairs:
#   L4 / R4  -- additional shoulder buttons above L1/R1
#   PL / PR  -- left / right back paddles
# They are probed and documented here for completeness; they are NOT written
# into the virtual DS4 report because DualSense / DualSense Edge emulation
# (which has slots for paddles via JSMASK_PADDLELEFT/RIGHT) is not supported
# by ViGEm Bus. If a future virtual-device layer gains that support, each
# entry here has a preferred JSL target listed in the comment.
#
# Default firmware ships the extras as aliases of existing buttons
# (L4 = X+L2 combo, R4 = Select, PL = L3, PR = R3). The dedicated bits
# below are only emitted after the aliases are cleared in 8BitDo Ultimate
# Software -- verified 2026-04-19 by tools/controller_mapper.py with zero
# co-firing on the old alias bits during the session.
EXTRA_BUTTONS = {
    "L4":  (10, 0x01),  # -> DualSense TouchPad / DualSense Edge FL1
    "R4":  (10, 0x02),  # -> DualSense Mute     / DualSense Edge FR1
    "PL":  (8,  0x20),  # -> DualSense Edge JSMASK_PADDLELEFT
    "PR":  (8,  0x04),  # -> DualSense Edge JSMASK_PADDLERIGHT
}

# ── ViGEm ctypes bindings ──────────────────────────────────────────────────────

VIGEM_ERROR_NONE = 0x20000000


def _find_vigem_dll() -> str | None:
    candidates = [
        r"C:\Windows\System32\ViGEmClient.dll",
        r"C:\Program Files\Nefarius Software Solutions\ViGEm Bus Driver\ViGEmClient.dll",
    ]
    try:
        import vgamepad as _vg
        # vgamepad bundles the DLL under vigem/client/x64/
        pkg_dir = os.path.dirname(_vg.__file__)
        # vgamepad 0.1.x layout: <pkg>/win/vigem/client/x64/
        # older layout:          <pkg>/vigem/client/x64/
        for subpath in (
            os.path.join("win",  "vigem", "client", "x64", "ViGEmClient.dll"),
            os.path.join("vigem", "client", "x64", "ViGEmClient.dll"),
        ):
            candidates.insert(0, os.path.join(pkg_dir, subpath))
    except ImportError:
        pass
    return next((p for p in candidates if os.path.isfile(p)), None)


class DS4_REPORT_EX(ctypes.Structure):
    _fields_ = [("Report", ctypes.c_uint8 * 63)]


class ViGemDS4:
    """Thin ctypes wrapper — creates one virtual DS4 and sends DS4_REPORT_EX updates."""

    def __init__(self, dll_path: str | None = None):
        path = dll_path or VIGEM_DLL_PATH or _find_vigem_dll()
        if not path:
            raise RuntimeError(
                "ViGEmClient.dll not found.\n"
                "Install ViGEm Bus: https://github.com/nefarius/ViGEmBus/releases\n"
                "Or: pip install vgamepad  (bundles the DLL)"
            )

        lib = ctypes.windll.LoadLibrary(path)

        lib.vigem_alloc.restype                     = ctypes.c_void_p
        lib.vigem_alloc.argtypes                    = []
        lib.vigem_free.restype                      = None
        lib.vigem_free.argtypes                     = [ctypes.c_void_p]
        lib.vigem_connect.restype                   = ctypes.c_uint32
        lib.vigem_connect.argtypes                  = [ctypes.c_void_p]
        lib.vigem_disconnect.restype                = None
        lib.vigem_disconnect.argtypes               = [ctypes.c_void_p]
        lib.vigem_target_ds4_alloc.restype          = ctypes.c_void_p
        lib.vigem_target_ds4_alloc.argtypes         = []
        lib.vigem_target_free.restype               = None
        lib.vigem_target_free.argtypes              = [ctypes.c_void_p]
        lib.vigem_target_add.restype                = ctypes.c_uint32
        lib.vigem_target_add.argtypes               = [ctypes.c_void_p, ctypes.c_void_p]
        lib.vigem_target_remove.restype             = ctypes.c_uint32
        lib.vigem_target_remove.argtypes            = [ctypes.c_void_p, ctypes.c_void_p]
        lib.vigem_target_ds4_update_ex.restype      = ctypes.c_uint32
        lib.vigem_target_ds4_update_ex.argtypes     = [
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(DS4_REPORT_EX),
        ]

        self._lib    = lib
        self._client = lib.vigem_alloc()
        self._target = None

        err = lib.vigem_connect(self._client)
        if err != VIGEM_ERROR_NONE:
            raise RuntimeError(
                f"vigem_connect failed: 0x{err:08X}\n"
                "Is the ViGEm Bus service running?  Run: sc start ViGEmBus"
            )

        self._target = lib.vigem_target_ds4_alloc()
        err = lib.vigem_target_add(self._client, self._target)
        if err != VIGEM_ERROR_NONE:
            raise RuntimeError(f"vigem_target_add failed: 0x{err:08X}")

    def update(self, report_bytes: bytes) -> None:
        """Push a 63-byte DS4 HID report (gyro at offsets 12–17)."""
        if len(report_bytes) != 63:
            raise ValueError(f"Expected 63 bytes, got {len(report_bytes)}")
        ex = DS4_REPORT_EX()
        ctypes.memmove(ex.Report, report_bytes, 63)
        self._lib.vigem_target_ds4_update_ex(self._client, self._target, ctypes.byref(ex))

    def close(self) -> None:
        if self._target:
            self._lib.vigem_target_remove(self._client, self._target)
            self._lib.vigem_target_free(self._target)
            self._target = None
        if self._client:
            self._lib.vigem_disconnect(self._client)
            self._lib.vigem_free(self._client)
            self._client = None

    def __enter__(self):  return self
    def __exit__(self, *_): self.close()


# ── HID device ─────────────────────────────────────────────────────────────────

def open_8bitdo() -> hid.device:
    """Return an open hid.device for the 8BitDo in DInput mode."""
    for info in hid.enumerate(VID, PID):
        dev = hid.device()
        dev.open_path(info["path"])
        return dev
    raise RuntimeError(
        f"8BitDo DInput device (VID={VID:#06x} PID={PID:#06x}) not found.\n"
        "Check:\n"
        "  • DInput mode: hold B during power-on (LED blinks blue)\n"
        "  • 8BitDo Ultimate Software closed: right-click tray icon → Exit"
    )


# ── Report parsing ─────────────────────────────────────────────────────────────

def _dpad_to_ds4(raw: bytes) -> int:
    """Convert 8BitDo DPad bytes to DS4 nibble (0=N ... 7=NW, 8=released).

    Verified 2026-04-19 by controller_mapper.py: DPad lives in the low
    nibble of byte 1. All 8 directions empirically confirmed --
      N=0x0  NE=0x1  E=0x2  SE=0x3  S=0x4  SW=0x5  W=0x6  NW=0x7
    -- values 0x0-0x7 match DS4's encoding 1:1. Idle is 0xF on the
    8BitDo vs 0x8 on DS4, so anything >= 8 is normalized to 8.
    """
    nibble = raw[1] & 0x0F
    return nibble if nibble < 8 else 8


def parse_8bitdo(raw: bytes) -> dict:
    """Unpack a 34-byte 8BitDo DInput report into named fields.

    Byte 14 battery encoding is from SDL's first-party HIDAPI driver
    (SDL_hidapi_8bitdo.c in libsdl-org/SDL):
      bit 7     = charging flag
      bits 0-6  = battery level percent (0-100)

    Bytes 27-30 on firmwares that expose it are a 32-bit LE device
    timestamp; our firmware returns zeros there, so we ignore it.
    """
    gx, gy, gz = struct.unpack_from("<3h", raw, 21)
    ax, ay, az = struct.unpack_from("<3h", raw, 15)
    batt_byte  = raw[14]
    return {
        "lx": raw[2], "ly": raw[3],
        "rx": raw[4], "ry": raw[5],
        "lt": raw[6], "rt": raw[7],
        "gx": gx, "gy": gy, "gz": gz,
        "ax": ax, "ay": ay, "az": az,
        "batt_pct":  batt_byte & 0x7F,
        "charging": (batt_byte & 0x80) != 0,
        "raw": raw,
    }


def _ds4_battery_byte(pct: int, charging: bool) -> int:
    """Encode an 8BitDo (0-100 %, charging flag) into a DS4 battery byte.

    DS4 convention:
      bits 0-3 = battery level 0-10 (10 = full, 0 = empty)
      bit  4   = charging / cable present
    """
    level = min(10, max(0, pct // 10))
    return level | (0x10 if charging else 0x00)


# ── DS4 report builder ─────────────────────────────────────────────────────────

def build_ds4_report(p: dict, ts_tick: int) -> bytes:
    """Translate a parsed 8BitDo dict into a 63-byte DS4 HID report.

    DS4 report layout (63 bytes, report ID stripped — fed via DS4_REPORT_EX):
      [0]     LX         [1]  LY         [2]  RX         [3]  RY
      [4]     dpad(3:0) Square(4) Cross(5) Circle(6) Triangle(7)
      [5]     L1(0) R1(1) L2d(2) R2d(3) Share(4) Options(5) L3(6) R3(7)
      [6]     PS(0) TP(1) counter(7:2)
      [7]     L2 analog  [8]  R2 analog
      [9-10]  Timestamp uint16 LE (188 µs/tick)
      [11]    Battery
      [12-13] Gyro X int16 LE   [14-15] Gyro Y   [16-17] Gyro Z
      [18-19] Accel X int16 LE  [20-21] Accel Y  [22-23] Accel Z
      [24-62] Zeros
    """
    buf = bytearray(63)
    raw = p["raw"]

    # Sticks — same 0-255 range and 0x80 centre on both controllers
    buf[0] = p["lx"]
    buf[1] = p["ly"]
    buf[2] = p["rx"]
    buf[3] = p["ry"]

    # DPad → DS4 nibble in bits 3:0 of byte 4
    buf[4] = _dpad_to_ds4(raw) & 0x0F

    def bit(src_byte: int, src_mask: int) -> int:
        return 1 if (raw[src_byte] & src_mask) else 0

    # Face buttons → DS4 byte 4 bits 4–7
    buf[4] |= bit(*BUTTON_MAP["X"]) << 4   # Square
    buf[4] |= bit(*BUTTON_MAP["B"]) << 5   # Cross
    buf[4] |= bit(*BUTTON_MAP["A"]) << 6   # Circle
    buf[4] |= bit(*BUTTON_MAP["Y"]) << 7   # Triangle

    # Shoulder + stick clicks → DS4 byte 5
    buf[5]  = bit(*BUTTON_MAP["L1"])     << 0
    buf[5] |= bit(*BUTTON_MAP["R1"])     << 1
    buf[5] |= bit(*BUTTON_MAP["L2d"])    << 2
    buf[5] |= bit(*BUTTON_MAP["R2d"])    << 3
    buf[5] |= bit(*BUTTON_MAP["Select"]) << 4
    buf[5] |= bit(*BUTTON_MAP["Start"])  << 5
    buf[5] |= bit(*BUTTON_MAP["L3"])     << 6
    buf[5] |= bit(*BUTTON_MAP["R3"])     << 7

    # Home/PS → DS4 byte 6 bit 0
    buf[6] = bit(*BUTTON_MAP["Home"]) << 0

    # Analog triggers (0–255)
    buf[7] = p["lt"]
    buf[8] = p["rt"]

    # Timestamp — JoyShockLibrary uses this for gyro integration timing
    struct.pack_into("<H", buf, 9, ts_tick & 0xFFFF)

    # Battery — forwarded from 8BitDo byte 14 (bit7=charging, bits0-6=percent)
    buf[11] = _ds4_battery_byte(p["batt_pct"], p["charging"])

    # Gyro — raw int16 pass-through: both controllers use 2000 dps / 32767 LSB
    # JSL sign convention: pitch = -GyroY, yaw = +GyroZ, roll = -GyroX
    # 8BitDo convention:   pitch = -gy,    yaw = +gz,    roll = -gx  (FINDINGS)
    # → identical mapping, so values are copied directly without transformation
    struct.pack_into("<3h", buf, 12, p["gx"], p["gy"], p["gz"])

    # Accel — 8BitDo: 1 g = 4096 LSB; DS4/JSL: 1 g = 8192 LSB → multiply by 2
    ax2 = max(-32768, min(32767, p["ax"] * 2))
    ay2 = max(-32768, min(32767, p["ay"] * 2))
    az2 = max(-32768, min(32767, p["az"] * 2))
    struct.pack_into("<3h", buf, 18, ax2, ay2, az2)

    return bytes(buf)


# ── Bridge loop ────────────────────────────────────────────────────────────────

_HEADER = (
    "jsm_bridge  |  8BitDo DInput -> virtual DS4 for JoyShockMapper\n"
    "Controls   |  Ctrl-C to quit\n"
    + "-" * 60
)


def _status(msg: str) -> None:
    sys.stdout.write(f"\r{msg:<70}")
    sys.stdout.flush()


def run_bridge() -> None:
    print(_HEADER, flush=True)

    print("Opening 8BitDo HID device... ", end="", flush=True)
    controller = open_8bitdo()
    print("OK")

    print("Creating virtual DS4 via ViGEm... ", end="", flush=True)
    with ViGemDS4() as ds4:
        print("OK")
        print("JoyShockMapper should now see a DualShock 4.")
        print("Open JoyShockMapper and press F1 (CONNECT) before rotating the controller.\n")

        # Timestamp counter — DS4 uses 188 µs ticks
        ts_tick      = 0
        ts_increment = round(POLL_INTERVAL / 188e-6)

        reports_sent = 0
        fresh        = 0
        last_stat    = time.monotonic()
        last_p       = None   # holds last valid parsed report for status display
        running      = True

        def _stop(sig, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT,  _stop)
        signal.signal(signal.SIGTERM, _stop)

        while running:
            t0  = time.monotonic()
            raw = bytes(controller.read(REPORT_LEN, timeout_ms=int(POLL_INTERVAL * 1000)))

            if raw and len(raw) >= REPORT_LEN and raw[0] == 0x01:
                p       = parse_8bitdo(raw)
                last_p  = p
                report  = build_ds4_report(p, ts_tick)
                ds4.update(report)
                ts_tick      = (ts_tick + ts_increment) & 0xFFFF
                reports_sent += 1
                fresh        += 1

            now = time.monotonic()
            if now - last_stat >= 1.0:
                if last_p:
                    pitch_dps = -last_p["gy"] * GYRO_SCALE
                    yaw_dps   =  last_p["gz"] * GYRO_SCALE
                    batt_tag  = f"{last_p['batt_pct']:3d}%{'+chg' if last_p['charging'] else '    '}"
                    _status(
                        f"Hz={fresh:3d}  "
                        f"gyro pitch={pitch_dps:+7.1f}  yaw={yaw_dps:+7.1f} dps  "
                        f"batt={batt_tag}  "
                        f"sent={reports_sent}"
                    )
                else:
                    _status("Waiting for controller data...")
                fresh     = 0
                last_stat = now

            elapsed = time.monotonic() - t0
            if elapsed < POLL_INTERVAL:
                time.sleep(POLL_INTERVAL - elapsed)

        print("\nShutting down... ", end="", flush=True)
    controller.close()
    print("Done.")


def main() -> None:
    try:
        run_bridge()
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


# ── Button probe (run with --probe to discover your button bit layout) ─────────

def run_probe() -> None:
    """Interactive probe: press each button and note which bits change in bytes 8-13.

    Captures every state transition in the button region and prints the
    affected (byte, bit) pairs plus the raw block in binary. Update
    BUTTON_MAP, EXTRA_BUTTONS, and _dpad_to_ds4() with the results.

    Buttons to press during the probe (17 total):
      Standard (13): B A X Y  L1 R1 L2 R2  Select Start  L3 R3  Home
      Extras (4):    L4 R4  PL PR
      Also exercise: DPad Up / Right / Down / Left
    """
    print("Opening 8BitDo HID device for button probe...")
    dev = open_8bitdo()
    print("Device open. Press each button one at a time. Ctrl-C to stop.\n")
    print("Suggested order:")
    print("  Face:    B, A, X, Y")
    print("  Shoulder: L1, R1, L2, R2, L4, R4")
    print("  System:  Select, Start, L3, R3, Home")
    print("  Paddles: PL, PR")
    print("  DPad:    Up, Right, Down, Left\n")
    # Watch bytes 8-13 (known button region) plus 10-13 overlap and bytes
    # outside that range in case DPad or other inputs live elsewhere.
    # We skip the sensor/timestamp block entirely.
    WATCH_RANGES = [(1, 2), (8, 14)]  # byte 1 = header/status, 8-13 = buttons
    # Note: sticks (2-5) and triggers (6-7) produce analog noise, so we skip
    # them by default. If DPad is analog-encoded there, press --probe-full instead.

    print(f"Watching bytes: {WATCH_RANGES}")
    print(f"{'bytes 1, 8-13 binary':<72}  changed-bits")
    print("-" * 120)

    def snapshot(r: bytes) -> bytes:
        return b"".join(r[a:b] for (a, b) in WATCH_RANGES)

    prev = bytes(sum(b - a for (a, b) in WATCH_RANGES))
    try:
        while True:
            raw = bytes(dev.read(REPORT_LEN, timeout_ms=20))
            if not raw or raw[0] != 0x01:
                continue
            snap = snapshot(raw)
            if snap == prev:
                continue

            # Map flat snapshot index back to real byte index for diff labels
            idx_map = []
            for (a, b) in WATCH_RANGES:
                idx_map.extend(range(a, b))

            diffs = []
            for flat_i, real_i in enumerate(idx_map):
                xor = snap[flat_i] ^ prev[flat_i]
                for bit in range(8):
                    if xor & (1 << bit):
                        state = "on" if (snap[flat_i] & (1 << bit)) else "off"
                        diffs.append(f"byte{real_i}.bit{bit}={state}")

            display = " ".join(
                f"{snap[i]:08b}" for i in range(len(snap))
            )
            diff_s = ", ".join(diffs) if diffs else "(no change)"
            print(f"{display:<72}  {diff_s}")
            prev = snap
    except KeyboardInterrupt:
        print("\n\nProbe complete.")
        print("If DPad still didn't register, run `--probe-full` to watch every byte.")
    finally:
        dev.close()


def run_probe_full() -> None:
    """Probe ALL 34 bytes of the HID report. Useful if DPad lives in the stick
    region (encoded as POV hat on an analog axis) or somewhere unexpected.
    """
    print("Opening 8BitDo HID device for FULL-report probe...")
    dev = open_8bitdo()
    print("Device open. Press buttons / DPad directions. Ctrl-C to stop.\n")
    print("Watching all 34 bytes. Stick drift may cause noise in bytes 2-5.\n")

    prev = bytes(REPORT_LEN)
    try:
        while True:
            raw = bytes(dev.read(REPORT_LEN, timeout_ms=20))
            if not raw or len(raw) < REPORT_LEN or raw[0] != 0x01:
                continue
            if raw == prev:
                continue

            diffs = []
            for i in range(REPORT_LEN):
                if raw[i] != prev[i]:
                    # Skip known analog regions to reduce noise
                    if i in (9, 10) or 15 <= i <= 26:  # timestamp + sensors
                        continue
                    diffs.append(f"byte{i}: {prev[i]:#04x}->{raw[i]:#04x}")

            if diffs:
                print("  " + ", ".join(diffs))
            prev = raw
    except KeyboardInterrupt:
        print("\nFull probe complete.")
    finally:
        dev.close()


if __name__ == "__main__":
    if "--probe-full" in sys.argv:
        run_probe_full()
    elif "--probe" in sys.argv:
        run_probe()
    else:
        main()
