#!/usr/bin/env python3
"""
protondb-tuner — host system profiler.

Probes the machine the skill is invoked on for the data points that shape a
recommendation, so the output is grounded in the real host instead of a
hardcoded default. The big one is GPU vendor: on an AMD box this makes the
recommender drop NVIDIA-only parameters (NVAPI/DLSS/…) outright, and vice versa.

Pure stdlib; only reads /sys, /proc, /etc, env, and `shutil.which`. Every probe
is best-effort and degrades to "unknown" rather than failing. Emits JSON
(default) or a human summary (--explain).
"""
import json
import os
import platform
import re
import shutil
import sys

DRM = "/sys/class/drm"
PCI_VENDOR = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "INTEL"}
WRAPPERS = ["gamemoderun", "game-performance", "mangohud", "mangoapp", "gamescope", "prime-run"]
COMPAT_DIRS = [
    "~/.steam/steam/compatibilitytools.d",
    "~/.local/share/Steam/compatibilitytools.d",
    "~/.steam/root/compatibilitytools.d",
]
# Directory names in compatibilitytools.d that are not selectable Proton runtimes.
NOT_RUNTIMES = {"legacyruntime", "steamtinkerlaunch"}


def detect_gpus():
    """Enumerate display-class GPUs from /sys/class/drm; classify vendor + role."""
    gpus = []
    try:
        cards = sorted(d for d in os.listdir(DRM) if re.fullmatch(r"card\d+", d))
    except OSError:
        cards = []
    for card in cards:
        base = os.path.join(DRM, card, "device")
        vid = _read(os.path.join(base, "vendor"))
        cls = _read(os.path.join(base, "class"))
        if not vid or not (cls or "").startswith("0x03"):  # 0x03 = display controller
            continue
        vendor = PCI_VENDOR.get(vid, f"OTHER({vid})")
        # 0x038000 = "display controller / other" is how Intel/AMD iGPUs commonly report;
        # 0x030000 = VGA. Treat Intel as iGPU; NVIDIA as dGPU; AMD ambiguous.
        role = "igpu" if vendor == "INTEL" else ("dgpu" if vendor == "NVIDIA" else "gpu")
        gpus.append({"card": card, "vendor": vendor, "role": role})
    return gpus


def primary_vendor(gpus):
    """The GPU a user games on: prefer a discrete NVIDIA/AMD over an Intel iGPU."""
    vendors = [g["vendor"] for g in gpus]
    for v in ("NVIDIA", "AMD", "INTEL"):
        if v in vendors:
            return v
    return vendors[0] if vendors else "UNKNOWN"


def detect_display():
    t = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if t in ("wayland", "x11"):
        return t
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def detect_distro():
    info = {}
    try:
        with open("/etc/os-release") as fh:
            for line in fh:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    info[k] = v.strip().strip('"')
    except OSError:
        pass
    return {"id": info.get("ID", "unknown"), "like": info.get("ID_LIKE", ""), "name": info.get("NAME", "")}


def detect_ntsync():
    if os.path.exists("/dev/ntsync"):
        return True
    m = re.match(r"(\d+)\.(\d+)", platform.release())
    if m and (int(m.group(1)), int(m.group(2))) >= (6, 14):
        return True
    return False


def detect_nvidia():
    txt = _read("/proc/driver/nvidia/version") or ""
    ver = None
    m = re.search(r"\b(\d+\.\d+\.\d+)\b", txt)
    if m:
        ver = m.group(1)
    is_open = "open kernel module" in txt.lower()
    if not txt:  # fall back to modinfo (license: Dual MIT/GPL => open kmod)
        lic = _cmd(["modinfo", "-F", "license", "nvidia"])
        if lic:
            is_open = "GPL" in lic
            ver = ver or (_cmd(["modinfo", "-F", "version", "nvidia"]) or None)
    return {"present": bool(txt) or shutil.which("nvidia-smi") is not None,
            "driver": ver, "open_kmod": is_open}


def detect_proton_builds():
    seen, builds = set(), []
    for d in COMPAT_DIRS:
        d = os.path.expanduser(d)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            low = name.lower()
            if name in seen or low in NOT_RUNTIMES:
                continue
            kind = ("cachyos" if "cachyos" in low else
                    "ge" if "ge-proton" in low or low.startswith("ge") else
                    "experimental" if "experimental" in low else
                    "official" if low.startswith("proton") else None)
            if kind:
                seen.add(name)
                builds.append({"name": name, "kind": kind})
    return builds


def detect_tools():
    return {t: shutil.which(t) is not None for t in WRAPPERS}


def _read(path):
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return None


def _cmd(argv):
    import subprocess
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None


def detect():
    gpus = detect_gpus()
    distro = detect_distro()
    nv = detect_nvidia()
    builds = detect_proton_builds()
    return {
        "gpus": gpus,
        "gpu": primary_vendor(gpus),
        "hybrid": len(gpus) >= 2,
        "display": detect_display(),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
        "distro": distro["id"],
        "distro_name": distro["name"],
        "kernel": platform.release(),
        "ntsync": detect_ntsync(),
        "cpu_cores": os.cpu_count(),
        "deck": distro["id"] in ("steamos",) or "steamdeck" in distro["name"].lower(),
        "tools": detect_tools(),
        "proton_builds": builds,
        "nvidia_driver": nv["driver"],
        "nvidia_open_kmod": nv["open_kmod"],
    }


def explain(p):
    gpu_list = ", ".join(f"{g['vendor']}/{g['role']}" for g in p["gpus"]) or "none found"
    inst = ", ".join(b["name"] for b in p["proton_builds"]) or "none in compatibilitytools.d"
    tools = ", ".join(k for k, v in p["tools"].items() if v) or "none"
    return "\n".join([
        f"GPU(s)        : {gpu_list}  → primary {p['gpu']}" + (" (hybrid)" if p["hybrid"] else ""),
        f"NVIDIA driver : {p['nvidia_driver'] or '—'}" + (" (open kmod)" if p["nvidia_open_kmod"] else ""),
        f"Display       : {p['display']} · {p['desktop']}",
        f"Distro/kernel : {p['distro_name'] or p['distro']} · {p['kernel']}",
        f"ntsync        : {'yes (/dev/ntsync)' if p['ntsync'] else 'no'}   CPU cores: {p['cpu_cores']}",
        f"Wrappers      : {tools}",
        f"Proton builds : {inst}",
    ])


if __name__ == "__main__":
    prof = detect()
    if "--explain" in sys.argv:
        print(explain(prof))
    else:
        print(json.dumps(prof, indent=2))
