"""
gyro_meter.py — live gyro angular velocity monitor

Reads the controller's IMU and shows pitch+yaw combined magnitude in
deg/sec, the same unit Steam Input uses in its "precision speed"
slider. Useful for understanding what values your hand motions
actually produce, and for eyeballing tremor / wiggle / echo / stepping
behaviour at the *input* end of the pipeline (before the precision
curve, smoothing, threshold, game smoothing, etc).

Two gyro sources, tried in this order:

  1. SDL GameController sensor API — works when SDL has a HIDAPI driver
     for the pad (Switch Pro, DualSense, Steam Deck, 8BitDo in NS mode).
  2. Raw HID via hidapi — used for 8BitDo Ultimate 2 Wireless in
     DInput mode (VID 0x2DC8 / PID 0x6012), which SDL does not expose
     sensors for. Requires firmware ≥ v1.03 (the user's pad is v1.09).

Requires:
    pip install pysdl2 pysdl2-dll
    pip install hidapi                (only needed for DInput path)

Running it:
    python gyro_meter.py

Controller-access notes (Windows):
 - 8BitDo pads only expose the IMU in certain modes:
     * NS / Switch mode (hold Y while powering on) — uses SDL path.
     * DInput mode      (hold B while powering on) — uses raw HID.
     * PC / XInput mode                            — no gyro exposed.
 - If Steam is running, Steam Input usually hides the raw pad. Options:
     a) Quit Steam entirely, then launch this script.
     b) In Steam, right-click the controller and turn "Steam Input
        Per-Game Setting" OFF for desktop / this app.
     c) Add this script to Steam as a Non-Steam Game; when launched
        through Steam it will receive gyro via Steam Input's SDL shim.
 - For DInput mode specifically, also close "8BitDo Ultimate Software"
   (right-click tray → Exit) — it holds the HID device exclusively.

Hotkeys:
 c   — calibrate bias (hold controller still for 1 second)
 r   — reset peak + zone stats + rest buffer
 m   — recenter virtual cursor mockup
 Esc — quit
"""

import ctypes
import math
import struct
import time
import tkinter as tk
from collections import deque

import sdl2


# ---- config ---------------------------------------------------------------
SAMPLE_HZ      = 200                        # gyro poll rate
PLOT_SECONDS   = 10                         # graph window length
REST_THRESH    = 1.0                        # deg/s ceiling for "at rest"
REST_WINDOW    = SAMPLE_HZ * 3              # rolling rest buffer size
PRECISION_REF  = 15.0                       # highlighted reference line
CALIB_SECONDS  = 1.0

# Virtual-cursor mockup settings
SCREEN_W       = 3840                       # target screen horiz. pixels
SCREEN_H       = 2160                       # target screen vert.  pixels
VIRT_SCALE     = 10                         # 1 px on-screen : N px real
VIRT_W         = SCREEN_W // VIRT_SCALE     # = 480
VIRT_H         = SCREEN_H // VIRT_SCALE     # = 270
DP360_DEFAULT  = 6680.0
SENS_DEFAULT   = 2.5
TRAIL_SECONDS  = 1.0                        # how long to keep cursor trail

# (upper_bound_exclusive, label, band_bg, accent, description)
#
# Bands tuned so PRIMARY is where realistic *controlled* motion lives,
# not just menu crawling. precision_speed (15 °/s) sits inside the SLOW
# band — below it the curve scales speed down; above it the curve is
# pass-through. Most gameplay yaw lands in PRIMARY or QUICK.
ZONES = [
    (  3.0, "REST",    "#0d0f18", "#89a",
     "still / below noise floor"),
    ( 20.0, "SLOW",    "#0d1222", "#6af",
     "fine precision, below or near precision_speed"),
    ( 80.0, "PRIMARY", "#0d2214", "#3e6",
     "primary controlled motion"),
    (200.0, "QUICK",   "#221d0d", "#ee6",
     "quick pan / correction"),
    (500.0, "FLICK",   "#220a08", "#f55",
     "aim flick"),
    (float("inf"), "SNAP", "#2a0606", "#f33",
     "violent / reflex flick"),
]

RAD2DEG = 180.0 / math.pi


def zone_index(speed):
    for i, z in enumerate(ZONES):
        if speed < z[0]:
            return i
    return len(ZONES) - 1


# ---- SDL init -------------------------------------------------------------
if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER | sdl2.SDL_INIT_SENSOR) < 0:
    raise SystemExit("SDL init failed: " + sdl2.SDL_GetError().decode())


def open_first_gyro_pad():
    n = sdl2.SDL_NumJoysticks()
    for i in range(n):
        if not sdl2.SDL_IsGameController(i):
            continue
        pad = sdl2.SDL_GameControllerOpen(i)
        if not pad:
            continue
        if sdl2.SDL_GameControllerHasSensor(pad, sdl2.SDL_SENSOR_GYRO):
            sdl2.SDL_GameControllerSetSensorEnabled(
                pad, sdl2.SDL_SENSOR_GYRO, sdl2.SDL_TRUE
            )
            name = sdl2.SDL_GameControllerName(pad)
            name = name.decode(errors="replace") if name else "controller"
            return pad, name
        sdl2.SDL_GameControllerClose(pad)
    return None, None


def enumeration_report():
    """Build a short report of what SDL is seeing, for failure messages."""
    lines = []
    n = sdl2.SDL_NumJoysticks()
    lines.append("SDL_NumJoysticks() = {}".format(n))
    for i in range(n):
        name = sdl2.SDL_JoystickNameForIndex(i)
        name = name.decode(errors="replace") if name else "<no name>"
        is_gc = bool(sdl2.SDL_IsGameController(i))
        guid = sdl2.SDL_JoystickGetDeviceGUID(i)
        guid_buf = (ctypes.c_char * 33)()
        sdl2.SDL_JoystickGetGUIDString(guid, guid_buf, 33)
        guid_str = guid_buf.value.decode()
        gyro = "n/a"
        if is_gc:
            gc = sdl2.SDL_GameControllerOpen(i)
            if gc:
                gyro = "yes" if sdl2.SDL_GameControllerHasSensor(
                    gc, sdl2.SDL_SENSOR_GYRO
                ) else "no"
                sdl2.SDL_GameControllerClose(gc)
        lines.append(
            "  [{}] {!r}  GUID={}  is_controller={}  gyro={}"
            .format(i, name, guid_str, is_gc, gyro)
        )
    return "\n".join(lines)


# ---- DInput-mode gyro source (raw HID) -----------------------------------
#
# SDL has no sensor-capable driver for 8BitDo VID 0x2DC8 / PID 0x6012 in
# DInput mode. The pad DOES transmit gyro in its HID input report though —
# report ID 0x01, sensor block at bytes 15..26 (int16 LE × 6, accel then
# gyro). Verified against SDL_hidapi_8bitdo.c and empirical probing of
# the user's pad on firmware v1.09.
#
# Firmware gating: pre-v1.03 firmware sends a 12-byte report with no
# sensors. We detect that via len(report) < 27 and refuse the source.

DINPUT_VID             = 0x2DC8
DINPUT_PID             = 0x6012
DINPUT_REPORT_ID       = 0x01
DINPUT_SENSOR_OFFSET   = 15
DINPUT_MIN_REPORT_SIZE = 27        # sensor block ends at byte 26
DINPUT_READ_SIZE       = 64
DINPUT_READ_TIMEOUT_MS = 50

GYRO_SCALE  = 2000.0 / 32767.0     # int16 → °/s
ACCEL_SCALE =    1.0 /  4096.0     # int16 → g  (currently unused)


def open_ultimate2_dinput():
    """Return (dev, name) if an 8BitDo Ultimate 2 Wireless in DInput
    mode is accessible, else (None, None). Caller closes via dev.close().

    Failure modes (all return None, None):
      - hidapi not installed
      - pad absent / in a different mode
      - HID interface already claimed (8BitDo Ultimate Software is the
        usual culprit — it holds the device exclusively while running).
    """
    try:
        import hid
    except ImportError:
        return None, None

    matches = hid.enumerate(DINPUT_VID, DINPUT_PID)
    if not matches:
        return None, None

    # Prefer the Generic Desktop Gamepad collection (usage_page=1 usage=5)
    target = next(
        (m for m in matches
         if m.get("usage_page") == 0x01 and m.get("usage") == 0x05),
        matches[0],
    )

    dev = hid.device()
    try:
        dev.open_path(target["path"])
    except (OSError, IOError):
        return None, None

    name = target.get("product_string") or "8BitDo Ultimate 2 (DInput)"
    return dev, name


class HIDGyroSource:
    """Non-blocking-ish wrapper around the DInput HID stream. Returns
    (pitch_dps, yaw_dps, roll_dps) — identical semantics to what the
    SDL path produces after RAD2DEG conversion, so the rest of poll()
    doesn't need to care which source is active.

    Axis mapping (from SDL_hidapi_8bitdo.c, preserved so both sources
    produce the same sign conventions downstream):
        pitch = -gy
        yaw   = +gz
        roll  = -gx
    """

    def __init__(self, dev, name):
        self.dev  = dev
        self.name = name

    def read_fresh(self):
        try:
            raw = self.dev.read(DINPUT_READ_SIZE,
                                timeout_ms=DINPUT_READ_TIMEOUT_MS)
        except (OSError, IOError):
            return None
        if not raw or len(raw) < DINPUT_MIN_REPORT_SIZE:
            return None
        if raw[0] != DINPUT_REPORT_ID:
            return None
        _ax, _ay, _az, gx, gy, gz = struct.unpack_from(
            "<hhhhhh", bytes(raw), DINPUT_SENSOR_OFFSET,
        )
        pitch_dps = -gy * GYRO_SCALE
        yaw_dps   =  gz * GYRO_SCALE
        roll_dps  = -gx * GYRO_SCALE
        return pitch_dps, yaw_dps, roll_dps

    def close(self):
        try:
            self.dev.close()
        except Exception:
            pass


# ---- Select a gyro source: SDL first, raw HID as fallback ---------------
source_kind = None
source_obj  = None
pad_name    = None

_sdl_pad, _sdl_name = open_first_gyro_pad()
if _sdl_pad is not None:
    source_kind = "sdl"
    source_obj  = _sdl_pad
    pad_name    = _sdl_name
else:
    _hid_dev, _hid_name = open_ultimate2_dinput()
    if _hid_dev is not None:
        source_kind = "hid"
        source_obj  = HIDGyroSource(_hid_dev, _hid_name)
        pad_name    = _hid_name

if source_kind is None:
    report = enumeration_report()
    raise SystemExit(
        "No gyro source found.\n"
        "\n"
        "{}\n"
        "\n"
        "Hints:\n"
        " - SDL only exposes gyro when it has a dedicated HIDAPI driver\n"
        "   for the pad (DualShock/DualSense, Switch Pro, Steam Deck,\n"
        "   8BitDo in NS mode).\n"
        " - For 8BitDo Ultimate 2 Wireless:\n"
        "     a) NS mode (hold Y on power-on) — uses the SDL path.\n"
        "     b) DInput mode (hold B on power-on) + `pip install hidapi`\n"
        "        — uses raw HID. Also close 8BitDo Ultimate Software\n"
        "        (right-click tray → Exit), which holds HID exclusively.\n"
        " - If is_controller=True but gyro=no above, SDL found the pad\n"
        "   but its driver for this device does not expose sensors.\n"
        " - If Steam is running it may be hiding the pad entirely.\n"
        .format(report)
    )

print("Gyro source:", source_kind, "-", pad_name)


# ---- state ----------------------------------------------------------------
samples     = deque(maxlen=SAMPLE_HZ * PLOT_SECONDS)  # (t, speed)
rest_buf    = deque(maxlen=REST_WINDOW)               # |speed| samples while resting
zone_counts = [0] * len(ZONES)
total_count = 0
peak        = 0.0

pitch_bias  = 0.0
yaw_bias    = 0.0

calibrating = False
calib_start = 0.0
calib_pitch = []
calib_yaw   = []

# Virtual cursor state (real-screen pixel coords)
virt_x      = SCREEN_W / 2.0
virt_y      = SCREEN_H / 2.0
trail       = deque(maxlen=int(SAMPLE_HZ * TRAIL_SECONDS))

# Polling-rate detection
last_raw    = (0.0, 0.0, 0.0)
fresh_times = deque(maxlen=400)   # timestamps of fresh (changed) samples

status_msg  = ""


# ---- Tk UI ----------------------------------------------------------------
root = tk.Tk()
root.title("Gyro meter — " + pad_name)
root.configure(bg="#111")

font_big      = ("Consolas", 60, "bold")
font_dominant = ("Consolas", 26, "bold")
font_med      = ("Consolas", 16)
font_small    = ("Consolas", 12)
font_mono     = ("Consolas", 12)

current_var   = tk.StringVar(value="  0.00")
peak_var      = tk.StringVar(value="peak   0.00 °/s")
dominant_var  = tk.StringVar(value="dominant: —")
stats_var     = tk.StringVar(value="")
status_var    = tk.StringVar(value="")
controls_text = ("c = calibrate bias    m = recenter virtual cursor    "
                 "r = reset stats    esc = quit")

CANVAS_W = 960
STRIP_H  = 96
STACK_H  = 28

# Header row — controls on the left (always visible), status on the right
header = tk.Frame(root, bg="#161616")
header.pack(fill="x")
tk.Label(header, text=controls_text, fg="#9ab", bg="#161616",
         font=font_small).pack(side="left", padx=14, pady=6)
tk.Label(header, textvariable=status_var, fg="#fc6", bg="#161616",
         font=font_small).pack(side="right", padx=14, pady=6)

tk.Label(root, text="deg / sec (pitch+yaw magnitude)",
         fg="#888", bg="#111", font=font_small).pack(pady=(10, 0))
current_label = tk.Label(root, textvariable=current_var,
                         fg="#3e6", bg="#111", font=font_big)
current_label.pack()
peak_label = tk.Label(root, textvariable=peak_var,
                      fg="#f90", bg="#111", font=font_med)
peak_label.pack()

dominant_label = tk.Label(root, textvariable=dominant_var,
                          fg="#888", bg="#111", font=font_dominant)
dominant_label.pack(pady=(6, 2))

stack_canvas = tk.Canvas(root, width=CANVAS_W, height=STACK_H,
                         bg="#000", highlightthickness=0)
stack_canvas.pack(padx=12, pady=(0, 6))

# Live zone-strip: shows at a glance which zone the CURRENT speed is in.
# Each zone = an equal-width coloured segment. Current zone is lit up
# in its accent colour; others are dim. A white needle inside the
# current segment shows position within that zone's range.
strip_canvas = tk.Canvas(root, width=CANVAS_W, height=STRIP_H,
                         bg="#000", highlightthickness=0)
strip_canvas.pack(padx=12, pady=(0, 10))

tk.Label(root, textvariable=stats_var, fg="#ccc", bg="#111",
         font=font_mono, justify="left").pack(anchor="w", padx=14)

# ---- virtual-cursor mockup ----
virt_frame = tk.Frame(root, bg="#111")
virt_frame.pack(anchor="w", padx=14, pady=(8, 4))

tk.Label(virt_frame,
         text="virtual cursor preview — {}×{} @ DP360 × sens, no filtering"
              .format(SCREEN_W, SCREEN_H),
         fg="#888", bg="#111", font=font_small).pack(anchor="w")

cfg_row = tk.Frame(virt_frame, bg="#111")
cfg_row.pack(anchor="w", pady=(2, 4))
tk.Label(cfg_row, text="DP360:", fg="#aaa", bg="#111",
         font=font_mono).pack(side="left")
dp360_entry = tk.Entry(cfg_row, width=8, font=font_mono,
                       bg="#222", fg="#fff", insertbackground="#fff")
dp360_entry.insert(0, str(int(DP360_DEFAULT)))
dp360_entry.pack(side="left", padx=(4, 12))
tk.Label(cfg_row, text="sens:", fg="#aaa", bg="#111",
         font=font_mono).pack(side="left")
sens_entry = tk.Entry(cfg_row, width=6, font=font_mono,
                      bg="#222", fg="#fff", insertbackground="#fff")
sens_entry.insert(0, str(SENS_DEFAULT))
sens_entry.pack(side="left", padx=(4, 12))

scale_info_var = tk.StringVar(value="")
tk.Label(cfg_row, textvariable=scale_info_var, fg="#7ab",
         bg="#111", font=font_small).pack(side="left", padx=(8, 0))

virt_canvas = tk.Canvas(virt_frame, width=VIRT_W, height=VIRT_H,
                        bg="#0a0a10", highlightthickness=1,
                        highlightbackground="#333")
virt_canvas.pack(anchor="w", pady=(0, 10))


def current_scale():
    """Read DP360 / sens from the entry fields with fallback."""
    try:
        dp = float(dp360_entry.get())
    except ValueError:
        dp = DP360_DEFAULT
    try:
        sn = float(sens_entry.get())
    except ValueError:
        sn = SENS_DEFAULT
    if dp <= 0 or sn <= 0:
        return DP360_DEFAULT, SENS_DEFAULT
    return dp, sn


def graph_y(speed, ymax):
    return CANVAS_H - int((speed / ymax) * (CANVAS_H - 10)) - 4


# ---- polling + update -----------------------------------------------------
DT        = 1.0 / SAMPLE_HZ
t0        = time.perf_counter()
sens_buf  = (ctypes.c_float * 3)()


def poll():
    global peak, total_count
    global calibrating, pitch_bias, yaw_bias
    global virt_x, virt_y
    global last_raw

    # Fetch a fresh gyro triple from whichever source is active.
    # Both paths emit pitch/yaw/roll in °/s after this block.
    if source_kind == "sdl":
        sdl2.SDL_GameControllerUpdate()
        rc = sdl2.SDL_GameControllerGetSensorData(
            source_obj, sdl2.SDL_SENSOR_GYRO, sens_buf, 3
        )
        if rc != 0:
            root.after(int(DT * 1000), poll)
            return
        raw_pitch = sens_buf[0] * RAD2DEG
        raw_yaw   = sens_buf[1] * RAD2DEG
        raw_roll  = sens_buf[2] * RAD2DEG
    else:  # "hid"
        vals = source_obj.read_fresh()
        if vals is None:
            root.after(int(DT * 1000), poll)
            return
        raw_pitch, raw_yaw, raw_roll = vals

    # Polling-rate detection: only count a sample as "fresh" if the
    # raw IMU triple changed since last poll. SDL returns the most
    # recent value on every call; duplicates = we're polling faster
    # than the device reports. The HID path already filters stale
    # reads (returns None) but running this check on both sources
    # keeps the fresh_times counter semantically identical.
    now_t = time.perf_counter() - t0
    new_raw = (raw_pitch, raw_yaw, raw_roll)
    if new_raw != last_raw:
        fresh_times.append(now_t)
        last_raw = new_raw

    # bias subtraction
    pitch = raw_pitch - pitch_bias
    yaw   = raw_yaw   - yaw_bias

    speed = math.hypot(pitch, yaw)
    t = time.perf_counter() - t0

    # calibration capture
    if calibrating:
        calib_pitch.append(raw_pitch)
        calib_yaw.append(raw_yaw)
        if t - calib_start >= CALIB_SECONDS:
            pitch_bias = sum(calib_pitch) / len(calib_pitch)
            yaw_bias   = sum(calib_yaw)   / len(calib_yaw)
            calibrating = False
            status_var.set(
                "calibrated: pitch_bias={:+.3f} yaw_bias={:+.3f} °/s"
                .format(pitch_bias, yaw_bias)
            )

    samples.append((t, speed))
    if speed > peak:
        peak = speed
    if speed < REST_THRESH:
        rest_buf.append(speed)
    zone_counts[zone_index(speed)] += 1
    total_count += 1

    # integrate raw pitch/yaw into the virtual-cursor mockup
    # Steam Input convention: yaw → horizontal, pitch → vertical.
    # Screen y grows downward; pitch-up should raise the cursor.
    # Yaw sign is flipped so pad-pan-right = cursor-right in the mock.
    if not calibrating:
        dp360, sens = current_scale()
        counts_per_deg = dp360 * sens / 360.0
        dx = -yaw   * DT * counts_per_deg
        dy = -pitch * DT * counts_per_deg
        virt_x = max(0.0, min(float(SCREEN_W), virt_x + dx))
        virt_y = max(0.0, min(float(SCREEN_H), virt_y + dy))
        trail.append((virt_x, virt_y))

    root.after(int(DT * 1000), poll)


def redraw():
    if not samples:
        root.after(33, redraw)
        return

    latest = samples[-1][1]
    cur_zi = zone_index(latest)
    cur_zone = ZONES[cur_zi]

    current_var.set("{:6.2f}".format(latest))
    current_label.configure(fg=cur_zone[3])

    peak_zi = zone_index(peak)
    peak_var.set("peak {:6.2f} °/s  ({})".format(peak, ZONES[peak_zi][1]))
    peak_label.configure(fg=ZONES[peak_zi][3])

    # --- live zone strip ---------------------------------------------------
    strip_canvas.delete("all")
    n = len(ZONES)
    seg_w = CANVAS_W / n

    for i, (upper, name, bg, accent, desc) in enumerate(ZONES):
        x0 = int(i * seg_w)
        x1 = int((i + 1) * seg_w)
        is_current = (i == cur_zi)

        # current zone = full accent bg; others = very dim bg
        fill = accent if is_current else bg
        strip_canvas.create_rectangle(x0, 0, x1, STRIP_H,
                                      fill=fill, outline="")

        # separator
        if i > 0:
            strip_canvas.create_line(x0, 0, x0, STRIP_H, fill="#000")

        # name — dark text on the lit-up current zone, accent elsewhere
        name_fg = "#000" if is_current else accent
        name_font = ("Consolas", 18, "bold") if is_current \
                    else ("Consolas", 13, "bold")
        strip_canvas.create_text((x0 + x1) // 2, 22,
                                 text=name, fill=name_fg,
                                 font=name_font)

        # range hint
        if upper == float("inf"):
            prev_upper = ZONES[i - 1][0] if i > 0 else 0.0
            range_text = "≥ {:g}".format(prev_upper)
        else:
            prev_upper = ZONES[i - 1][0] if i > 0 else 0.0
            range_text = "{:g}–{:g} °/s".format(prev_upper, upper)
        range_fg = "#222" if is_current else "#555"
        strip_canvas.create_text((x0 + x1) // 2, 42,
                                 text=range_text, fill=range_fg,
                                 font=("Consolas", 10))

        # on the current zone, drop in a description under the range
        if is_current:
            strip_canvas.create_text((x0 + x1) // 2, 60,
                                     text=desc, fill="#000",
                                     font=("Consolas", 9, "italic"))

    # position needle inside the current zone's segment
    cur_lower = ZONES[cur_zi - 1][0] if cur_zi > 0 else 0.0
    cur_upper = cur_zone[0]
    if cur_upper == float("inf"):
        cur_upper = max(cur_lower * 2.0, cur_lower + 100.0)
    span = cur_upper - cur_lower
    within = (latest - cur_lower) / span if span > 0 else 0.5
    within = max(0.0, min(1.0, within))
    x_seg = int(cur_zi * seg_w)
    x_mark = int(x_seg + within * seg_w)

    # needle: a bold white bar at the bottom of the strip with a
    # small triangle pointing up. Shows position *within* the current
    # zone's range. Exact numeric value is already shown in the big
    # readout at the top of the window.
    strip_canvas.create_line(x_mark, STRIP_H - 18,
                             x_mark, STRIP_H - 2,
                             fill="#fff", width=3)
    strip_canvas.create_polygon(
        x_mark,         STRIP_H - 22,
        x_mark - 6,     STRIP_H - 12,
        x_mark + 6,     STRIP_H - 12,
        fill="#fff", outline="",
    )

    # --- dominant zone + stacked proportions bar ---
    stack_canvas.delete("all")
    if total_count > 0:
        # dominant zone
        dom_i = max(range(len(ZONES)), key=lambda i: zone_counts[i])
        dom_pct = zone_counts[dom_i] / total_count * 100.0
        dom_zone = ZONES[dom_i]
        dominant_var.set(
            "dominant:  {}  {:.0f}%   — {}"
            .format(dom_zone[1], dom_pct, dom_zone[4])
        )
        dominant_label.configure(fg=dom_zone[3])

        # stacked bar — one contiguous horizontal bar split by time-share
        x = 0
        for i, (upper, name, bg, accent, _desc) in enumerate(ZONES):
            cnt = zone_counts[i]
            if cnt == 0:
                continue
            w = int(round(CANVAS_W * cnt / total_count))
            if w <= 0:
                continue
            stack_canvas.create_rectangle(
                x, 0, x + w, STACK_H, fill=accent, outline=""
            )
            pct = cnt / total_count * 100.0
            if w >= 42:
                stack_canvas.create_text(
                    x + w / 2, STACK_H / 2,
                    text="{} {:.0f}%".format(name, pct),
                    fill="#000", font=("Consolas", 10, "bold"),
                )
            x += w
    else:
        dominant_var.set("dominant: —   (collecting samples…)")
        dominant_label.configure(fg="#888")

    # --- rest stats ---
    lines = []
    if len(rest_buf) >= 30:
        m = sum(rest_buf) / len(rest_buf)
        var = sum((x - m) ** 2 for x in rest_buf) / len(rest_buf)
        std = math.sqrt(var)
        mx  = max(rest_buf)
        lines.append(
            "rest (<{:.1f} °/s): mean {:4.2f}  stddev {:4.2f}  max {:4.2f}  n={}"
            .format(REST_THRESH, m, std, mx, len(rest_buf))
        )
    else:
        lines.append("rest: collecting…  (hold still)")
    lines.append("bias subtracted:  pitch {:+.3f}  yaw {:+.3f} °/s"
                 .format(pitch_bias, yaw_bias))

    # Polling-rate + jitter report
    if len(fresh_times) >= 3:
        window_lo = fresh_times[-1] - 1.0    # last 1 second
        recent = [t for t in fresh_times if t >= window_lo]
        if len(recent) >= 3:
            deltas = [recent[i] - recent[i-1]
                      for i in range(1, len(recent))]
            mean_dt = sum(deltas) / len(deltas)
            rate = 1.0 / mean_dt if mean_dt > 0 else 0.0
            dmean = sum(deltas) / len(deltas)
            dvar  = sum((x - dmean) ** 2 for x in deltas) / len(deltas)
            jitter_ms = math.sqrt(dvar) * 1000.0
            lines.append(
                "sensor update rate:  {:5.1f} Hz   "
                "mean dt {:5.2f} ms   jitter (1σ) {:4.2f} ms"
                .format(rate, mean_dt * 1000.0, jitter_ms)
            )
    else:
        lines.append("sensor update rate: measuring…")

    stats_var.set("\n".join(lines))

    # --- virtual cursor preview ---
    dp360, sens = current_scale()
    counts_per_deg = dp360 * sens / 360.0
    horiz_sweep_deg = SCREEN_W / counts_per_deg if counts_per_deg else 0.0
    scale_info_var.set(
        "{:.1f} counts/°    full-width sweep = {:.1f}°    "
        "1 °/s = {:.1f} px/s"
        .format(counts_per_deg, horiz_sweep_deg, counts_per_deg)
    )

    sx = VIRT_W / SCREEN_W
    sy = VIRT_H / SCREEN_H
    virt_canvas.delete("all")

    # centerline crosshair reference (faint)
    virt_canvas.create_line(VIRT_W / 2, 0, VIRT_W / 2, VIRT_H, fill="#222")
    virt_canvas.create_line(0, VIRT_H / 2, VIRT_W, VIRT_H / 2, fill="#222")

    # live cursor position (top-left) + screen dims (bottom-right)
    virt_canvas.create_text(3, 3,
                            text="{:.0f}, {:.0f}".format(virt_x, virt_y),
                            anchor="nw",
                            fill="#888", font=("Consolas", 9))
    virt_canvas.create_text(VIRT_W - 3, VIRT_H - 3,
                            text="{}×{}".format(SCREEN_W, SCREEN_H),
                            anchor="se", fill="#333", font=("Consolas", 8))

    # trail with age-fade
    n = len(trail)
    if n >= 2:
        tlist = list(trail)
        # draw in segments with progressively brighter fill for recency
        for i in range(1, n):
            age = (n - i) / n   # 0 (newest) .. 1 (oldest)
            # ramp colour from dark grey (#223) to accent of current zone
            accent = ZONES[cur_zi][3]
            # parse accent to rgb
            r = int(accent[1], 16) * 17
            g = int(accent[2], 16) * 17
            b = int(accent[3], 16) * 17
            # blend with dark
            blend = 1.0 - age
            col = "#{:02x}{:02x}{:02x}".format(
                int(r * blend + 10 * (1 - blend)),
                int(g * blend + 10 * (1 - blend)),
                int(b * blend + 18 * (1 - blend)),
            )
            x0, y0 = tlist[i - 1]
            x1, y1 = tlist[i]
            virt_canvas.create_line(
                x0 * sx, y0 * sy, x1 * sx, y1 * sy,
                fill=col, width=1,
            )

    # cursor marker — crosshair + dot
    cx = virt_x * sx
    cy = virt_y * sy
    virt_canvas.create_line(cx - 8, cy, cx + 8, cy, fill="#fff")
    virt_canvas.create_line(cx, cy - 8, cx, cy + 8, fill="#fff")
    virt_canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2,
                            outline="#fff", fill="#fff")

    root.after(50, redraw)


def on_key(e):
    global peak, total_count, calibrating, calib_start, calib_pitch, calib_yaw
    global virt_x, virt_y
    k = e.keysym.lower()
    if k == "r":
        peak = 0.0
        for i in range(len(zone_counts)):
            zone_counts[i] = 0
        total_count = 0
        rest_buf.clear()
        status_var.set("reset")
    elif k == "c":
        calibrating = True
        calib_start = time.perf_counter() - t0
        calib_pitch = []
        calib_yaw   = []
        status_var.set("calibrating… hold still for {:.0f}s".format(CALIB_SECONDS))
    elif k == "m":
        virt_x = SCREEN_W / 2.0
        virt_y = SCREEN_H / 2.0
        trail.clear()
        status_var.set("virtual cursor recentered")
    elif k == "escape":
        root.quit()


root.bind("<Key>", on_key)

poll()
redraw()

try:
    root.mainloop()
finally:
    if source_kind == "sdl":
        try:
            sdl2.SDL_GameControllerClose(source_obj)
        except Exception:
            pass
    elif source_kind == "hid":
        source_obj.close()
    sdl2.SDL_Quit()
