#!/usr/bin/env python3
"""
mp-helper – cross-platform helper around `mpremote`

Sub-commands
------------
mp-helper list
    Print all detected MicroPython-compatible serial devices.

mp-helper upload
    Upload the files defined in FILE_PATTERNS (wildcards allowed)
    to a chosen device (interactive dropdown).

mp-helper dev
    Run the `main.py` that is in the current directory on a
    chosen device (interactive dropdown).

mp-helper fulldev
    Upload all configured files then run main.py (single device selection).
"""

import argparse, glob, os, platform, re, subprocess, sys, textwrap
from pathlib import Path
from typing import List, Optional, Tuple

# ------------------------------  USER SETTINGS  ------------------------------

# Edit this list (wildcards allowed) – all matching files are uploaded by
# `mp-helper upload`.  Relative paths are resolved from the script’s cwd.
FILE_PATTERNS: List[str] = [
    "boot.py",
    "main.py",
    "hal.py",
    "hardware.yaml",
    "studio.py",
    "AGENTS.md",
    "menu.py",
    "personality.py",

    "pin_values.py",
    "happy_meter.py",
    "buzzer_sounds.py",
    "ADXL345.py",
    "MPU6050.py",
    "oled_functions.py",
    "settings_store.py",
    "default_core.json",
    "custom_core.json",
    "custom_code/custom_code_*.py",
    "lib/**/*.py",
    "first_boot.py",
    "web_server.py",
    "www/**/*.html",
    "www/**/*.css",
    "www/**/*.js",
    "web/**/LICENSE-*"
    "*.bmp",
]

# -----------------------------------------------------------------------------


# === Serial-port discovery (cross-platform) ==================================
def _iter_pyserial_ports() -> List[Tuple[str, str]]:
    """
    Return list of (device, description) tuples, using pyserial if available,
    else minimal fall-back scanning.  Works on Linux, macOS, Windows.
    """
    try:
        import serial.tools.list_ports  # pyserial ≥3.0
        return [(p.device, p.description) for p in serial.tools.list_ports.comports()]
    except ImportError:                      # noqa: E722  (fallback)
        pat = {
            "Linux":  ["/dev/ttyACM*", "/dev/ttyUSB*"],
            "Darwin": ["/dev/tty.*", "/dev/cu.*"],
            "Windows": [r"COM[0-9]*"],
        }[platform.system()]
        devices: List[str] = []
        for g in pat:
            devices.extend(glob.glob(g))
        return [(d, "Serial port") for d in sorted(set(devices))]


def _resolve_shortcut(arg: str) -> str:
    """
    Map a/u/c shortcuts to real paths, otherwise return arg unchanged.
    """
    if re.fullmatch(r"[auc]\d+", arg):
        prefix, n = arg[0], int(arg[1:])
        osname = platform.system()
        if osname == "Windows":          # c<num> = COM<num>
            return f"COM{n}" if prefix == "c" else arg
        # *nix
        if prefix == "a":
            return f"/dev/ttyACM{n}"
        if prefix == "u":
            return f"/dev/ttyUSB{n}"
    return arg


def _preferred_device_index(devices: List[Tuple[str, str]]) -> Optional[int]:
    """Return index of preferred device or None if no clear preference.

    Preference order (first match wins by pattern order, then lowest numeric suffix):
    1. Strong device name patterns (per-OS) like ttyACM*, ttyUSB*, usbmodem*, usbserial*, SLAB_USBtoUART, wchusbserial.
    2. If none match by name, fall back to description keywords (ESP32, Pico, CP210, CH340, WCH, Silicon Labs).
    If still nothing, return None (no default selection).
    """
    if not devices:
        return None
    osname = platform.system()
    # Device name regexes (platform-specific plus common USB UART drivers)
    if osname == "Linux":
        dev_patterns = [
            r"/dev/ttyACM(\d+)$", r"/dev/ttyUSB(\d+)$", r"/dev/ttyCH341(\d+)$",
            r"/dev/ttyWCH(\d+)$", r"/dev/ttySLAB(\d+)$"
        ]
    elif osname == "Darwin":
        dev_patterns = [
            r"/dev/tty\.usbmodem(\d+)$", r"/dev/cu\.usbmodem(\d+)$",
            r"/dev/tty\.usbserial(\d+)$", r"/dev/cu\.usbserial(\d+)$",
            r"/dev/tty\.wchusbserial(\d+)$", r"/dev/cu\.wchusbserial(\d+)$",
            r"/dev/tty\.SLAB_USBtoUART(\d+)$", r"/dev/cu\.SLAB_USBtoUART(\d+)$"
        ]
    else:  # Windows
        dev_patterns = [r"COM(\d+)$"]

    desc_patterns = [
        r"ESP32", r"Pico", r"RP2040", r"CP210", r"CH340", r"WCH", r"Silicon Labs"
    ]

    best: Optional[Tuple[int, int, int]] = None  # (tier, pattern_order, numeric/id)
    best_idx: Optional[int] = None

    for idx, (dev, desc) in enumerate(devices):
        # Tier 0: device name patterns
        matched = False
        for order, pat in enumerate(dev_patterns):
            m = re.search(pat, dev)
            if m:
                try:
                    num = int(m.group(1))
                except Exception:
                    num = 0
                score = (0, order, num)
                if best is None or score < best:
                    best = score
                    best_idx = idx
                matched = True
                break
        if matched:
            continue
        # Tier 1: description patterns (no numeric extraction – use idx ordering)
        for order, pat in enumerate(desc_patterns):
            if re.search(pat, desc, re.IGNORECASE):
                score = (1, order, idx)
                if best is None or score < best:
                    best = score
                    best_idx = idx
                break

    return best_idx


# === Helpers =================================================================
def _pick_device() -> str:
    """Interactive selection with optional heuristic default.

    If a preferred device is found, ENTER selects it. Otherwise user must
    explicitly choose (no default). '0' rescans.
    """
    while True: # for rescanning
        devices = _iter_pyserial_ports()
        default_idx = None
        if not devices:
            print("No serial devices found.")
        else:
            default_idx = _preferred_device_index(devices)
            if default_idx is not None:
                print("Select device (ENTER for starred default, 0 to rescan):")
            else:
                print("Select device (no default, enter number, 0 to rescan):")

            for i, (dev, desc) in enumerate(devices):
                marker = "*" if default_idx is not None and i == default_idx else " "
                print(f"  [{i+1}] {marker} {dev:25} {desc}")
        
        while True: # for input
            if not devices:
                prompt = "Enter 0 to rescan: "
            else:
                default_prompt = f" (default {default_idx+1})" if default_idx is not None else ""
                prompt = f"Enter number{default_prompt}, or 0 to rescan: "
            
            raw = input(prompt).strip()

            if raw == '0':
                break # break inner loop to rescan

            if not devices:
                print("Invalid selection, try again.")
                continue

            if raw == "":
                if default_idx is not None:
                    return devices[default_idx][0]
                else:
                    print("No default available – please enter a number.")
                    continue
            try:
                choice = int(raw)
                if 1 <= choice <= len(devices):
                    return devices[choice - 1][0]
                else:
                    print("Invalid selection, try again.")
            except (ValueError, IndexError):
                print("Invalid selection, try again.")
        
        # This part is reached if raw == '0'
        print("\nRescanning...\n")


def _run_mpremote(*mpremote_args: str) -> None:
    """
    Execute mpremote with the supplied arguments.
    """
    cmd = ["mpremote", *mpremote_args]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        sys.exit("mpremote not found. `pip install mpremote` first.")
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


# Helper routines so fulldev can reuse logic
def _gather_files() -> List[Path]:
    files: List[Path] = []
    for pattern in FILE_PATTERNS:
        files.extend(Path().glob(pattern))
    return files


def _upload_files(port: str) -> None:
    files = _gather_files()
    if not files:
        sys.exit("No files matched FILE_PATTERNS.")
    for f in files:
        print(f"Uploading {f} → {port} …")
        _run_mpremote("connect", port, "fs", "cp", str(f), ":")
    print("Upload complete.")


def _run_main(port: str) -> None:
    main_local = Path("main.py")
    if not main_local.exists():
        sys.exit("main.py not found in current directory.")
    print(f"Running main.py on {port} …")
    _run_mpremote("connect", port, "fs", "cp", "main.py", ":")
    _run_mpremote("connect", port, "exec", "import main")


# === Sub-commands ============================================================
def cmd_list(_: argparse.Namespace) -> None:
    """
    mp-helper list
    """
    for dev, desc in _iter_pyserial_ports():
        print(f"{dev:15} {desc}")


def cmd_upload(_: argparse.Namespace) -> None:
    """
    mp-helper upload
    """
    port = _pick_device()
    _upload_files(port)


def cmd_dev(_: argparse.Namespace) -> None:
    """
    mp-helper dev
    """
    port = _pick_device()
    _run_main(port)


def cmd_fulldev(_: argparse.Namespace) -> None:
    """
    mp-helper fulldev
    """
    port = _pick_device()
    _upload_files(port)
    _run_main(port)


# === CLI entrypoint ==========================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mp-helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list",  help="List attached devices").set_defaults(func=cmd_list)
    sub.add_parser("upload", help="Upload files defined in FILE_PATTERNS").set_defaults(func=cmd_upload)
    sub.add_parser("dev",   help="Run main.py on device").set_defaults(func=cmd_dev)
    sub.add_parser("fulldev", help="Upload then run main.py").set_defaults(func=cmd_fulldev)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
