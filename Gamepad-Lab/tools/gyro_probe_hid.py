"""
gyro_probe_hid.py — raw HID byte-change probe for gyro detection.

Bypasses SDL entirely and reads the raw HID input reports from the pad.
Used when SDL's joystick API can't see gyro (confirmed for the
8BitDo Ultimate 2 Wireless in DInput mode VID=2DC8 PID=6012).

The approach: record per-byte min/max/total-motion across three
timed phases:

  IDLE    — pad still, sticks untouched. Baseline noise.
  STICKS  — move sticks and triggers only, pad body motionless.
  ROTATE  — hold sticks at rest, rotate the pad (pitch, yaw, roll).

Bytes that move MORE during ROTATE than STICKS are gyro candidates.
The script tries to pull the full HID report descriptor too, so we
can eyeball any non-standard usage pages (Motion = 0x05, or vendor).

Requires:
    pip install hid           (preferred)
  OR
    pip install hidapi        (also works; different API under the same
                               module name; the script auto-detects)

Run it in DInput mode, Steam closed. Follow the console prompts.
Output is written to `hid_probe_report.txt` in the working dir.
"""

import os
import sys
import time
from collections import namedtuple


try:
    import hid
except ImportError as e:
    raise SystemExit(
        "Failed to import 'hid' module.\n"
        "  {}\n\n"
        "On Windows this usually means both 'hid' and 'hidapi' are\n"
        "installed and are conflicting: the 'hid' package (pure Python)\n"
        "shadows 'hidapi' (compiled, bundles hidapi.dll), then fails\n"
        "because it can't find the hidapi DLL at import time.\n\n"
        "Fix:\n"
        "  pip uninstall -y hid\n"
        "  (this leaves 'hidapi' alone — its 'hid' module has the DLL\n"
        "   bundled and will import cleanly)\n"
        .format(e)
    )


TARGET_VID   = 0x2DC8
TARGET_PID   = 0x6012
READ_SIZE    = 64
READ_TIMEOUT = 50       # ms

# Phase list — (label, duration_s, console_instruction)
PHASES = [
    ("IDLE",   5,
     "Put the pad flat and do NOT touch it for 5 seconds."),
    ("STICKS", 10,
     "Move sticks + triggers + buttons only. Keep the pad body still."),
    ("ROTATE", 15,
     "Release sticks/triggers. Rotate the pad (pitch/yaw/roll) only."),
]


# ---- hidapi abstraction ---------------------------------------------------
def _detect_api():
    """Return a dict of callables suited for whichever package is present."""
    if hasattr(hid, "Device"):
        # The "hid" package from pypi.org/project/hid/
        def open_path(path):
            return hid.Device(path=path)
        def read(d, size):
            return d.read(size, timeout=READ_TIMEOUT)
        def close(d):
            d.close()
        def get_descriptor(d):
            fn = getattr(d, "get_report_descriptor", None)
            return fn() if fn else None
        return {"open": open_path, "read": read, "close": close,
                "descr": get_descriptor, "flavor": "hid"}
    if hasattr(hid, "device"):
        # The "hidapi" package
        def open_path(path):
            d = hid.device()
            d.open_path(path)
            return d
        def read(d, size):
            return d.read(size, timeout_ms=READ_TIMEOUT)
        def close(d):
            d.close()
        def get_descriptor(d):
            fn = getattr(d, "get_report_descriptor", None)
            return bytes(fn()) if fn else None
        return {"open": open_path, "read": read, "close": close,
                "descr": get_descriptor, "flavor": "hidapi"}
    raise SystemExit("The installed 'hid' module is unfamiliar to me.")


api = _detect_api()
print("Using hid package flavor:", api["flavor"])


# ---- device selection -----------------------------------------------------
matches = hid.enumerate(TARGET_VID, TARGET_PID)
if not matches:
    raise SystemExit(
        "No HID device matching VID={:04X} PID={:04X} found.\n"
        "Is the pad connected in DInput mode?".format(TARGET_VID, TARGET_PID)
    )

print()
print("Matched HID interfaces:")
for i, m in enumerate(matches):
    usage_page = m.get("usage_page")
    usage      = m.get("usage")
    iface      = m.get("interface_number")
    path       = m.get("path")
    if isinstance(path, bytes):
        path = path.decode(errors="replace")
    print("  [{}] usage_page=0x{:04x} usage=0x{:02x} iface={}  {}"
          .format(i, usage_page or 0, usage or 0,
                  iface if iface is not None else "?",
                  path))

# Prefer the Generic Desktop Gamepad (0x01/0x05) one
target = None
for m in matches:
    if m.get("usage_page") == 0x01 and m.get("usage") == 0x05:
        target = m
        break
if target is None:
    target = matches[0]

print()
print("Opening: usage_page=0x{:04x} usage=0x{:02x}"
      .format(target.get("usage_page") or 0, target.get("usage") or 0))

dev = api["open"](target["path"])


# ---- HID report descriptor ------------------------------------------------
descriptor_bytes = None
try:
    descriptor_bytes = api["descr"](dev)
    if descriptor_bytes:
        print("HID report descriptor: {} bytes captured."
              .format(len(descriptor_bytes)))
    else:
        print("HID report descriptor retrieval not supported by this hidapi.")
except Exception as e:
    print("HID report descriptor retrieval failed:", e)


# ---- sample collection ----------------------------------------------------
Stats = namedtuple("Stats", "samples first last bmin bmax motion first_bytes")

def new_stats():
    return {
        "samples":     0,
        "first":       None,
        "last":        None,
        "bmin":        [255] * READ_SIZE,
        "bmax":        [-1]  * READ_SIZE,
        "motion":      [0]   * READ_SIZE,
        "first_bytes": None,
    }


def pad(buf, size):
    if len(buf) < size:
        return bytes(buf) + bytes(size - len(buf))
    return bytes(buf[:size])


def drain(dev, seconds):
    """Consume reports for a fixed wall-clock duration, return stats."""
    s = new_stats()
    prev = None
    start = time.perf_counter()
    end = start + seconds
    next_tick = start + 1.0
    last_sample_count = 0
    while time.perf_counter() < end:
        data = api["read"](dev, READ_SIZE)
        if data:
            buf = pad(data, READ_SIZE)
            if s["first"] is None:
                s["first"] = time.perf_counter()
                s["first_bytes"] = buf
            s["last"] = time.perf_counter()
            s["samples"] += 1
            for i in range(READ_SIZE):
                b = buf[i]
                if b < s["bmin"][i]:
                    s["bmin"][i] = b
                if b > s["bmax"][i]:
                    s["bmax"][i] = b
                if prev is not None:
                    s["motion"][i] += abs(b - prev[i])
            prev = buf

        # once-per-second progress line — reassures the user that reports
        # are arriving and the phase is still active
        now = time.perf_counter()
        if now >= next_tick:
            elapsed = now - start
            remaining = max(0.0, end - now)
            per_sec = s["samples"] - last_sample_count
            last_sample_count = s["samples"]
            print("    t+{:>4.1f}s   {:>4.1f}s left   {:>3} reports this sec"
                  .format(elapsed, remaining, per_sec))
            next_tick += 1.0
    return s


# warm-up read so the first buf isn't cold
for _ in range(5):
    try:
        api["read"](dev, READ_SIZE)
    except Exception:
        pass


phase_results = {}

for label, dur, instruction in PHASES:
    print()
    print("=" * 64)
    print("Phase [{}] — {}".format(label, dur))
    print(instruction)
    for c in (3, 2, 1):
        print("  starting in {}…".format(c))
        time.sleep(1)
    print("  GO")
    s = drain(dev, dur)
    phase_results[label] = s
    print("  done — {} samples ({:.1f}/s effective)"
          .format(s["samples"],
                  s["samples"] / dur if dur > 0 else 0))

api["close"](dev)


# ---- analyze + write report ----------------------------------------------
out_path = "hid_probe_report.txt"

def fmt_bytes(buf):
    if buf is None:
        return "(none)"
    return " ".join("{:02x}".format(b) for b in buf)


lines = []
lines.append("=" * 72)
lines.append("gyro_probe_hid.py — raw HID byte-change session report")
lines.append("=" * 72)
lines.append("")
lines.append("VID / PID            : {:04X} / {:04X}".format(TARGET_VID, TARGET_PID))
lines.append("Read size per report : {} bytes".format(READ_SIZE))
lines.append("hid flavor in use    : {}".format(api["flavor"]))
lines.append("")

if descriptor_bytes is not None:
    lines.append("HID report descriptor ({} bytes):".format(len(descriptor_bytes)))
    # 16 bytes per row
    for off in range(0, len(descriptor_bytes), 16):
        chunk = descriptor_bytes[off:off + 16]
        lines.append("  {:04x}  {}".format(off, fmt_bytes(chunk)))
    lines.append("")
else:
    lines.append("HID report descriptor: unavailable on this hidapi flavor.")
    lines.append("")

# sample counts
lines.append("Samples per phase:")
for label, _, _ in PHASES:
    s = phase_results[label]
    lines.append("  {:<7} : {} samples".format(label, s["samples"]))
lines.append("")

# per-byte table across phases
lines.append("-" * 72)
lines.append("Per-byte activity across phases")
lines.append("-" * 72)
header = "{:>4} | ".format("b") + " | ".join(
    "{:^22}".format(label) for label, _, _ in PHASES
) + " |"
sub = "{:>4} | ".format("") + " | ".join(
    "{:^22}".format("min  max      Σ|Δ|") for _ in PHASES
) + " |"
lines.append(header)
lines.append(sub)
lines.append("-" * len(header))

for i in range(READ_SIZE):
    row = "{:>4} | ".format(i)
    for label, _, _ in PHASES:
        s = phase_results[label]
        mn, mx, mo = s["bmin"][i], s["bmax"][i], s["motion"][i]
        if s["samples"] == 0:
            row += "{:^22}".format("-") + " | "
        else:
            row += "{:>3d} {:>3d} {:>12d}".format(
                mn if mn != 255 else 0,
                mx if mx != -1  else 0,
                mo) + " | "
    lines.append(row.rstrip())
lines.append("")

# initial report per phase — useful to spot constant report-ID byte(s)
lines.append("First report captured in each phase (hex):")
for label, _, _ in PHASES:
    s = phase_results[label]
    lines.append("  {:<7} : {}".format(label, fmt_bytes(s["first_bytes"])))
lines.append("")

rotate = phase_results["ROTATE"]
sticks = phase_results["STICKS"]
idle   = phase_results["IDLE"]

# Classify every byte that moved at all. Three mutually exclusive classes:
#   "gyro"  — responds to ROTATE much more than STICKS (orientation-only)
#   "accel" — responds to BOTH ROTATE and STICKS, both well over IDLE
#             (motion sensor picking up housing vibration too, OR a sensor
#             high-byte flipping on each sign-cross)
#   "stick" — responds to STICKS much more than ROTATE (stick / trigger /
#             button-driven byte)
#
# Thresholds are loose because:
#   - stick bytes average ~0.1 per-sample Σ|Δ| even when saturated
#   - sensor HIGH bytes of int16 values move only when |value| crosses 256
MIN_ACTIVITY    = 0.08   # per-sample Σ|Δ| below this = "never moved"
IDLE_FLOOR      = 0.05   # avoid divide-by-zero vs. idle noise
OVER_IDLE       = 2.0    # a byte "responds" if its phase is > this × idle
CROSS_DOMINANCE = 1.5    # rotate-vs-sticks dominance threshold

rotate_s = rotate["samples"] or 1
sticks_s = sticks["samples"] or 1
idle_s   = idle["samples"]   or 1

gyro_bytes  = []
accel_bytes = []
stick_bytes = []
per_byte    = []

for i in range(READ_SIZE):
    r_n = rotate["motion"][i] / rotate_s
    s_n = sticks["motion"][i] / sticks_s
    n_n = idle["motion"][i]   / idle_s
    per_byte.append((i, r_n, s_n, n_n))

    if max(r_n, s_n) < MIN_ACTIVITY:
        continue  # byte is static

    floor = max(n_n, IDLE_FLOOR)
    rotate_responds = r_n > OVER_IDLE * floor
    sticks_responds = s_n > OVER_IDLE * floor

    if rotate_responds and sticks_responds:
        if r_n > s_n * CROSS_DOMINANCE:
            gyro_bytes.append((i, r_n, s_n, n_n))
        elif s_n > r_n * CROSS_DOMINANCE:
            stick_bytes.append((i, r_n, s_n, n_n))
        else:
            accel_bytes.append((i, r_n, s_n, n_n))
    elif rotate_responds:
        gyro_bytes.append((i, r_n, s_n, n_n))
    elif sticks_responds:
        stick_bytes.append((i, r_n, s_n, n_n))


def expand_with_high_bytes(byte_list, per_byte_map):
    """For each flagged byte N, also include N+1 if it shows any nonzero
    activity. Rationale: int16-LE high bytes only flip when the value
    crosses ±256, which is rare, so they often slip under the activity
    threshold even though they belong to the same logical field."""
    by_idx = {b[0] for b in byte_list}
    additions = []
    for i in sorted(by_idx):
        j = i + 1
        if j in by_idx or j not in per_byte_map:
            continue
        r_n, s_n, n_n = per_byte_map[j]
        if max(r_n, s_n) > 0.02:   # any motion at all
            additions.append((j, r_n, s_n, n_n))
    return sorted(byte_list + additions, key=lambda x: x[0])


def int16_pairs(byte_list):
    """Find adjacent (N, N+1) pairs within a flagged list that look like
    int16-LE (low byte ≥2× high byte activity during rotation or sticks).
    """
    by_index = {i: (i, r, s, n) for i, r, s, n in byte_list}
    pairs = []
    used = set()
    for i in sorted(by_index):
        if i in used or (i + 1) not in by_index:
            continue
        lo_r = by_index[i][1]
        lo_s = by_index[i][2]
        hi_r = by_index[i + 1][1]
        hi_s = by_index[i + 1][2]
        lo_max = max(lo_r, lo_s)
        hi_max = max(hi_r, hi_s)
        if lo_max >= 2.0 * max(hi_max, 0.02) and lo_max > 0.3:
            pairs.append((i, i + 1))
            used.add(i)
            used.add(i + 1)
    return pairs


# Expand gyro/accel groups to include the high byte of each int16 pair
per_byte_map = {i: (r, s, n) for i, r, s, n in per_byte}
gyro_bytes  = expand_with_high_bytes(gyro_bytes,  per_byte_map)
accel_bytes = expand_with_high_bytes(accel_bytes, per_byte_map)


def write_section(title, byte_list, explain):
    lines.append("-" * 72)
    lines.append(title)
    lines.append("-" * 72)
    if explain:
        lines.append(explain)
        lines.append("")
    if not byte_list:
        lines.append("  (none)")
        lines.append("")
        return
    lines.append("  byte    per-sample Σ|Δ|")
    lines.append("          rotate   sticks   idle")
    for i, r_n, s_n, n_n in sorted(byte_list, key=lambda x: -max(x[1], x[2])):
        lines.append(
            "  {:>3}     {:6.2f}   {:6.2f}   {:5.2f}"
            .format(i, r_n, s_n, n_n)
        )
    pairs = int16_pairs(byte_list)
    if pairs:
        lines.append("")
        lines.append("  int16-LE pairs (low, high): " +
                     ", ".join("({}, {})".format(a, b) for a, b in pairs))
    lines.append("")


write_section(
    "GYRO-LIKE BYTES — respond to rotation more than sticks",
    gyro_bytes,
    "These bytes move meaningfully more during ROTATE than STICKS.\n"
    "Rotation-specific. On 8BitDo Ultimate 2 Wireless (V1.03+ firmware)\n"
    "SDL's driver places the gyro at bytes 21–26 (three int16-LE axes).",
)

write_section(
    "ACCEL-LIKE BYTES — respond to both rotation and stick motion",
    accel_bytes,
    "These bytes move noticeably during both ROTATE and STICKS. Typical\n"
    "of an accelerometer: it picks up rotation *and* the housing shake\n"
    "caused by pressing buttons / flicking sticks. Also consistent with\n"
    "the HIGH byte of a sensor int16 that only flips on sign-cross.\n"
    "SDL's driver places the accel at bytes 15–20 on this pad.",
)

write_section(
    "STICK / TRIGGER BYTES — respond to sticks more than rotation",
    stick_bytes,
    "Input-driven bytes. Presence of at least two bytes here validates\n"
    "the probe is reading a live HID stream correctly.",
)


with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# --- console verdict ------------------------------------------------------
print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

sensor_like = gyro_bytes + accel_bytes
sensor_str  = ", ".join(str(b[0]) for b in sorted(sensor_like, key=lambda x: x[0]))

if sensor_like and stick_bytes:
    print("SENSOR BYTES FOUND in raw HID stream — bytes: " + sensor_str)
    print("Stick bytes also validated, so the probe is working.")
    print("Next step: decode these bytes as int16-LE to get gyro/accel values.")
elif sensor_like and not stick_bytes:
    print("Sensor bytes found, but no stick bytes validated — suspicious.")
    print("Re-run and make sure you actually move sticks during STICKS.")
elif not sensor_like and stick_bytes:
    print("NO SENSOR BYTES in HID reports for this pad+mode.")
    print("Stick bytes DID validate, so the probe is calibrated.")
    print("Conclusion: this mode does not transmit sensor data in reports.")
    print("For 8BitDo Ultimate 2: check firmware — v1.02 has 12-byte reports")
    print("(no sensors), v1.03+ has 34-byte reports with sensors at 15–26.")
else:
    print("Neither sensor nor stick bytes detected — probe did not receive")
    print("meaningful data. Re-run with actual input during each phase.")
print()
print("Full report:", os.path.abspath(out_path))
print("Report size:", os.path.getsize(out_path), "bytes")
