"""
protondb-tuner — shared extraction / normalization / hardware-bucketing logic.

Data source (established empirically, see MEMORY.md "protondb-config-inference"):
  bdefore/protondb-data ODbL dump -> reports_piiremoved.json
  flat JSON array of report objects; per-report `verdict` is BINARY yes/no
  ("did it run"), NOT a graded tier. `launchOptions` is the key tweak field
  (~14% of reports non-empty; ~84% of those carry the %command% token).

This module is imported by build_db.py / update_game.py / export_demo.py.
Nothing here touches the network or the DB; it is pure parsing + math helpers.
"""
import re
import math

# --------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------
HALFLIFE_MONTHS = 6.0          # exp-decay half-life for recency weighting
RECENT_WINDOW_MONTHS = 6.0     # "last-N-months" prevalence window
SECONDS_PER_MONTH = 30.44 * 86400.0
SMOOTH_K = 1.0                 # add-k pseudocount for smoothed lift (obs-vs-expected)
MIN_SUPPORT_CATALOG = 3        # min raw support for a param to enter the catalog ranking
MIN_SUPPORT_STORE = 2          # min raw support to persist a per-game param row

# Namespaces and the denominator population each is scored against.
# launchopts  -> reports with a non-empty launchOptions string
# variant     -> reports with responses.variant present
# customproton-> reports with responses.customProtonVersion present
# notes       -> reports with non-empty notes.verdict text
BASIS_LAUNCHOPTS = "launchopts"
BASIS_VARIANT = "variant"
BASIS_CUSTOMPROTON = "customproton"
BASIS_NOTES = "notes"

FAULT_KEYS = [
    "performanceFaults", "graphicalFaults", "audioFaults", "inputFaults",
    "windowingFaults", "stabilityFaults", "saveGameFaults", "significantBugs",
]

# --------------------------------------------------------------------------
# launchOptions tokenizer / normalizer
# --------------------------------------------------------------------------
# Known wrapper executables that legitimately precede %command%. Only these are
# emitted as wrapper params; other bare pre-tokens (e.g. gamescope resolution
# numbers) are ignored to avoid noise.
WRAPPERS = {
    "gamemoderun", "mangohud", "mangoapp", "gamescope", "game-performance",
    "prime-run", "primusrun", "optirun", "obs-gamecapture", "obs-vkcapture",
    "strangle", "libstrangle", "taskset", "nice", "umu-run", "steam-run",
    "pressure-vessel-wrap", "vblank_mode", "switcherooctl",
}

# Vars whose value is freeform / path-like / high-cardinality: collapse to <custom>.
BUCKET_VARS = {
    "WINEDLLOVERRIDES", "LD_PRELOAD", "LD_LIBRARY_PATH", "VK_ICD_FILENAMES",
    "VK_DRIVER_FILES", "VK_ADD_DRIVER_FILES", "DXVK_FILTER_DEVICE_NAME",
    "MANGOHUD_CONFIG", "MANGOHUD_CONFIGFILE", "VKBASALT_CONFIG_FILE",
    "WINE_CPU_TOPOLOGY", "PROTON_LOG_DIR", "DXVK_CONFIG_FILE",
    "DXVK_STATE_CACHE_PATH", "STEAM_COMPAT_DATA_PATH", "STEAM_COMPAT_MOUNTS",
    "STEAM_COMPAT_INSTALL_PATH", "PRESSURE_VESSEL_FILESYSTEMS_RW",
    "WINEPREFIX", "PROTONPATH", "PROTON_LOG", "__GL_SHADER_DISK_CACHE_PATH",
    "VKD3D_SHADER_CACHE_PATH", "MESA_SHADER_CACHE_DIR", "VKD3D_CONFIG_FILE",
    "WINEFSYNC_SPINCOUNT", "MANGOHUD_DLSYM",
}
# (PROTON_LOG values are usually paths or "1"; bucketed because the value is noise.)

# Vars whose value is a user-/monitor-specific number, not a knob identity: -> <num>.
NUM_VARS = {
    "DXVK_FRAME_RATE", "PULSE_LATENCY_MSEC", "MANGOHUD_FPS_LIMIT",
    "PROTON_FORCE_LARGE_ADDRESS_AWARE",  # 1/0 actually, handled by bool path
}

_ENV_RE = re.compile(r"""(?:^|[\s;"'])([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|'[^']*'|\S+)""")
_DOTTED_CVAR_RE = re.compile(r"^-?[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9_]+)+=\S+$")
_SHELLHACK_RE = re.compile(
    r"(\beval\b|\bsed\b|\bawk\b|`|\$\(|&&|\|\||\bunset\b|\bexport\b|"
    r"\bbash\s+-c\b|\bsh\s+-c\b|\bexec\b|\becho\b)"
)
_SIMPLE_VAL_RE = re.compile(r"^[A-Za-z0-9_.:+|/@-]{1,24}$")
_BOOL_MAP = {"true": "1", "on": "1", "yes": "1", "enabled": "1",
             "false": "0", "off": "0", "no": "0", "disabled": "0"}


def clean_value(var, raw):
    """Normalize an env value into a canonical, low-cardinality token."""
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    v = v.strip()
    if "%command%" in v:
        v = v.split("%command%")[0]
    v = v.strip(";, \t")
    if var in BUCKET_VARS:
        return "<custom>" if v else ""
    if not v:
        return ""
    low = v.lower()
    # boolean-ish (also rescue glued garbage like "1gamemoderun")
    m = re.match(r"^(0|1|true|false|on|off|yes|no|enabled|disabled)", low)
    if m and (low in _BOOL_MAP or low in ("0", "1") or not _SIMPLE_VAL_RE.match(v)):
        tok = m.group(1)
        return _BOOL_MAP.get(tok, tok)
    if var in NUM_VARS:
        return "<num>" if re.match(r"^[0-9]", v) else (v if _SIMPLE_VAL_RE.match(v) else "<custom>")
    # canonicalize comma-sets (order-insensitive), e.g. VKD3D_CONFIG=dxr,dxr11
    if "," in v and re.match(r"^[A-Za-z0-9_]+(,[A-Za-z0-9_]+)+$", v):
        return ",".join(sorted(p for p in v.split(",") if p))
    if _SIMPLE_VAL_RE.match(v):
        return v
    return "<custom>"


def _norm_arg(tok):
    """Canonicalize a post-%command% game argument (engine args are ~case-insensitive)."""
    t = tok.strip().strip(";,")
    if not t:
        return None
    # dotted UE cvar, possibly with leading '-'
    if _DOTTED_CVAR_RE.match(t):
        return t.lower()
    if t.startswith("-"):
        return t.lower()
    return None


def parse_launch_options(s):
    """
    Parse a launchOptions string into normalized parameter tuples.

    Returns a list of (namespace, key, value) tuples. namespace in:
      env       -> environment assignment (value normalized; '' when key-only)
      wrapper   -> known wrapper executable before %command%
      arg       -> game argument after %command%
      shellhack -> shell metaprogramming present (exe-swap / anti-cheat bypass etc.)
    Deduplicated within a single report.
    """
    out = set()
    if not s or not s.strip():
        return []
    low_junk = s.strip().lower()
    if low_junk in ("n/a", "na", "none", "-", "no", "nan", "null", "%command%"):
        return []

    # ENV: scan whole string so misplaced (post-%command%) envs are still captured.
    for m in _ENV_RE.finditer(s):
        var, raw = m.group(1), m.group(2)
        val = clean_value(var, raw)
        out.add(("env", var, val))

    # split on FIRST %command%
    if "%command%" in s:
        idx = s.index("%command%")
        pre, post = s[:idx], s[idx + len("%command%"):]
    else:
        pre, post = s, ""

    # WRAPPERS from pre-tokens (skip env assignments; handle gamescope arg run)
    pre_toks = re.split(r"[\s;]+", pre.strip())
    skip_gamescope_args = False
    for tok in pre_toks:
        t = tok.strip()
        if not t:
            continue
        if skip_gamescope_args:
            if t == "--":
                skip_gamescope_args = False
            continue
        if "=" in t and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            continue
        if t.startswith("-"):
            continue
        tl = t.lower()
        if tl in WRAPPERS:
            out.add(("wrapper", tl, ""))
            if tl == "gamescope":
                skip_gamescope_args = True

    # GAME ARGS: from post-%command% tokens; if there is NO %command%, Steam passes
    # the whole string as args, so scan the whole string for dash-args in that case.
    arg_region = post if "%command%" in s else s
    for tok in re.split(r"\s+", arg_region.strip()):
        a = _norm_arg(tok)
        if a:
            # a dotted cvar carries a value (r.foo=1); keep key=value as the param key
            out.add(("arg", a, ""))

    # SHELL-HACK detection (exe-swaps, eval/sed launcher or anti-cheat bypass)
    mh = _SHELLHACK_RE.search(s)
    if mh:
        kind = "anticheat" if re.search(r"eac|anticheat|anti-cheat|battleye|be_?service", s, re.I) else "generic"
        out.add(("shellhack", kind, ""))

    return sorted(out)


# --------------------------------------------------------------------------
# Proton-runtime params (variant / customProtonVersion / notes-mined versions)
# --------------------------------------------------------------------------
_GE_RE = re.compile(r"GE[- ]?Proton[\s-]?(\d+)[.\-](\d+)", re.I)
_PROTON_NUM_RE = re.compile(r"\bProton[\s-]?(\d+)\.(\d+)\b", re.I)
_PROTON_EXP_RE = re.compile(r"\bProton[\s-]?(experimental|hotfix|next)\b", re.I)


def normalize_custom_proton(name):
    """Canonicalize a GE/custom Proton build name, e.g. 'GE-Proton10-25'."""
    if not name:
        return None
    m = _GE_RE.search(name)
    if m:
        return f"GE-Proton{m.group(1)}-{m.group(2)}"
    return name.strip()[:32] or None


def mine_notes_versions(notes_text):
    """Extract Proton-version mentions from free-text notes. Returns set of canonical tokens."""
    out = set()
    if not notes_text:
        return out
    for m in _GE_RE.finditer(notes_text):
        out.add(f"GE-Proton{m.group(1)}-{m.group(2)}")
    for m in _PROTON_NUM_RE.finditer(notes_text):
        out.add(f"Proton-{m.group(1)}.{m.group(2)}")
    for m in _PROTON_EXP_RE.finditer(notes_text):
        out.add(f"Proton-{m.group(1).lower()}")
    return out


def notes_text(notes):
    """Flatten the notes dict (verdict/extra/etc.) into one searchable string."""
    if not notes:
        return ""
    if isinstance(notes, str):
        return notes
    if isinstance(notes, dict):
        return " ".join(str(v) for v in notes.values() if v)
    return ""


# --------------------------------------------------------------------------
# Hardware bucketing (free-text systemInfo -> coarse buckets)
# --------------------------------------------------------------------------
_NV_RE = re.compile(r"nvidia|geforce|\brtx\b|\bgtx\b|nvapi|nouveau|\bnv\d|quadro", re.I)
_AMD_RE = re.compile(r"\bamd\b|radeon|\bradv\b|\brx ?\d|navi|vega|\bgfx\d|amdgpu|raphael|"
                     r"phoenix|rembrandt|cezanne|renoir|\baco\b|polaris", re.I)
_INTEL_RE = re.compile(r"intel|\biris\b|\buhd\b|hd graphics|\barc\b|\bxe\b|i915|mesa intel|alchemist", re.I)
_DECK_RE = re.compile(r"steam ?deck|steamos|jupiter|galileo|valve.*van gogh|van gogh|aerith|sephiroth", re.I)


def gpu_vendor(si):
    g = (str(si.get("gpu", "")) + " " + str(si.get("gpuDriver", ""))).strip()
    if _NV_RE.search(g):
        return "NVIDIA"
    if _AMD_RE.search(g):
        return "AMD"
    if _INTEL_RE.search(g):
        return "INTEL"
    return "UNKNOWN"


def display_server(si, lo):
    """wayland / x11 / unknown — from xWindowManager, then launchOptions hints."""
    xwm = str(si.get("xWindowManager", "")).lower()
    if xwm:
        if "wayland" in xwm or "kwin_wayland" in xwm or "gnome shell" in xwm and "wayland" in xwm:
            return "wayland"
        if "x11" in xwm or "xorg" in xwm or "i3" in xwm or "kwin_x11" in xwm or "openbox" in xwm \
           or "bspwm" in xwm or "awesome" in xwm or "xfwm" in xwm:
            return "x11"
        if "wayland" in xwm:
            return "wayland"
    s = (lo or "").lower()
    if "proton_enable_wayland=1" in s or "sdl_videodriver='wayland'" in s or "sdl_videodriver=wayland" in s \
       or "sdl_video_driver=wayland" in s:
        return "wayland"
    if "sdl_videodriver=x11" in s or "sdl_video_driver=x11" in s:
        return "x11"
    return "unknown"


def is_steam_deck(si, lo):
    blob = " ".join(str(si.get(k, "")) for k in ("gpu", "cpu", "os", "kernel"))
    if _DECK_RE.search(blob):
        return True
    if re.search(r"steamdeck=1", (lo or ""), re.I):
        return True
    return False


# --------------------------------------------------------------------------
# Math helpers
# --------------------------------------------------------------------------
def smoothed_lift(support, denom, base_rate, k=SMOOTH_K):
    """
    Observed-vs-expected ratio, add-k smoothed toward 1.0 for low support.
      expected = denom * base_rate
      lift = (support + k) / (expected + k)
    base_rate is the global per-param prevalence in the matching denominator basis.
    """
    if denom <= 0 or base_rate <= 0:
        return 1.0
    expected = denom * base_rate
    return (support + k) / (expected + k)


def recency_weight(ts, now_ts, halflife_months=HALFLIFE_MONTHS):
    months = max(0.0, (now_ts - ts) / SECONDS_PER_MONTH)
    return 0.5 ** (months / halflife_months)


def months_ago(ts, now_ts):
    return (now_ts - ts) / SECONDS_PER_MONTH


def param_id(namespace, key, value):
    """Stable string id used as the param primary key in the DB and accumulators."""
    return f"{namespace}|{key}|{value}" if value else f"{namespace}|{key}|"


def param_display(namespace, key, value):
    """Human-readable form for catalogs/JSON."""
    if namespace == "env":
        return f"{key}={value}" if value else key
    if namespace == "wrapper":
        return key
    if namespace == "arg":
        return key
    if namespace == "shellhack":
        return f"shell-hack:{key}"
    if namespace == "proton":
        return f"{key}={value}" if value else key
    return param_id(namespace, key, value)
