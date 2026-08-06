"""
Windows 11 Key Remapper with Gaming Support
============================================
A robust key remapping tool that works with games and applications.
Uses low-level Windows hooks for maximum compatibility.

Requirements:
- Windows 11 (also works on Windows 10)
- Python 3.8+
- Administrator rights are optional. They are only needed to affect windows
  that themselves run elevated (some games, Task Manager, etc.).

Author: Key Remapper
License: MIT
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import atexit
import webbrowser
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Set, Tuple
from pathlib import Path
from enum import IntEnum

# Windows API Constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Mouse messages (only the buttons we allow remapping)
WM_MOUSEMOVE = 0x0200
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
LLKHF_INJECTED = 0x00000010
LLKHF_LOWER_IL_INJECTED = 0x00000002

# Key event types
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001

# Input type
INPUT_KEYBOARD = 1

# Unassigned virtual key used to "consume" a held Windows key so that releasing
# it does not pop the Start menu after we swallowed the real key press.
DUMMY_KEY = 0xFF

APP_NAME = "KeyRemapper"


def _default_config_dir() -> Path:
    """Per-user config directory (survives PyInstaller one-file extraction)."""
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"


CONFIG_DIR = _default_config_dir()
CONFIG_FILE = CONFIG_DIR / "key_remap_config.json"
LOG_FILE = CONFIG_DIR / "key_remapper.log"

# Older versions stored the config next to the script. Under a one-file build
# that path is a temp directory that Windows deletes on exit, so we only read
# from it (once) to migrate existing setups.
LEGACY_CONFIG_FILE = Path(__file__).parent / "key_remap_config.json"

logger = logging.getLogger(APP_NAME)


def setup_logging(level: int = logging.INFO) -> None:
    """Attach a rotating-ish file handler to the module logger (idempotent)."""
    if logger.handlers:
        return
    logger.setLevel(level)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())


setup_logging()


class VirtualKey(IntEnum):
    """Virtual Key Codes for Windows"""
    VK_LBUTTON = 0x01
    VK_RBUTTON = 0x02
    VK_CANCEL = 0x03
    VK_MBUTTON = 0x04
    VK_XBUTTON1 = 0x05
    VK_XBUTTON2 = 0x06
    VK_BACK = 0x08
    VK_TAB = 0x09
    VK_CLEAR = 0x0C
    VK_RETURN = 0x0D
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12  # Alt key
    VK_PAUSE = 0x13
    VK_CAPITAL = 0x14  # Caps Lock
    VK_ESCAPE = 0x1B
    VK_SPACE = 0x20
    VK_PRIOR = 0x21  # Page Up
    VK_NEXT = 0x22   # Page Down
    VK_END = 0x23
    VK_HOME = 0x24
    VK_LEFT = 0x25
    VK_UP = 0x26
    VK_RIGHT = 0x27
    VK_DOWN = 0x28
    VK_SELECT = 0x29
    VK_PRINT = 0x2A
    VK_EXECUTE = 0x2B
    VK_SNAPSHOT = 0x2C  # Print Screen
    VK_INSERT = 0x2D
    VK_DELETE = 0x2E
    VK_HELP = 0x2F
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    VK_APPS = 0x5D
    VK_SLEEP = 0x5F
    VK_NUMPAD0 = 0x60
    VK_NUMPAD1 = 0x61
    VK_NUMPAD2 = 0x62
    VK_NUMPAD3 = 0x63
    VK_NUMPAD4 = 0x64
    VK_NUMPAD5 = 0x65
    VK_NUMPAD6 = 0x66
    VK_NUMPAD7 = 0x67
    VK_NUMPAD8 = 0x68
    VK_NUMPAD9 = 0x69
    VK_MULTIPLY = 0x6A
    VK_ADD = 0x6B
    VK_SEPARATOR = 0x6C
    VK_SUBTRACT = 0x6D
    VK_DECIMAL = 0x6E
    VK_DIVIDE = 0x6F
    VK_F1 = 0x70
    VK_F2 = 0x71
    VK_F3 = 0x72
    VK_F4 = 0x73
    VK_F5 = 0x74
    VK_F6 = 0x75
    VK_F7 = 0x76
    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_F10 = 0x79
    VK_F11 = 0x7A
    VK_F12 = 0x7B
    VK_F13 = 0x7C
    VK_F14 = 0x7D
    VK_F15 = 0x7E
    VK_F16 = 0x7F
    VK_F17 = 0x80
    VK_F18 = 0x81
    VK_F19 = 0x82
    VK_F20 = 0x83
    VK_F21 = 0x84
    VK_F22 = 0x85
    VK_F23 = 0x86
    VK_F24 = 0x87
    VK_NUMLOCK = 0x90
    VK_SCROLL = 0x91
    VK_LSHIFT = 0xA0
    VK_RSHIFT = 0xA1
    VK_LCONTROL = 0xA2
    VK_RCONTROL = 0xA3
    VK_LMENU = 0xA4  # Left Alt
    VK_RMENU = 0xA5  # Right Alt
    VK_OEM_1 = 0xBA      # ;:
    VK_OEM_PLUS = 0xBB   # =+
    VK_OEM_COMMA = 0xBC  # ,<
    VK_OEM_MINUS = 0xBD  # -_
    VK_OEM_PERIOD = 0xBE # .>
    VK_OEM_2 = 0xBF      # /?
    VK_OEM_3 = 0xC0      # `~
    VK_OEM_4 = 0xDB      # [{
    VK_OEM_5 = 0xDC      # \|
    VK_OEM_6 = 0xDD      # ]}
    VK_OEM_7 = 0xDE      # '"
    # Multimedia / browser keys (common remap targets for the Copilot key)
    VK_BROWSER_BACK = 0xA6
    VK_BROWSER_FORWARD = 0xA7
    VK_BROWSER_REFRESH = 0xA8
    VK_BROWSER_STOP = 0xA9
    VK_BROWSER_SEARCH = 0xAA
    VK_BROWSER_FAVORITES = 0xAB
    VK_BROWSER_HOME = 0xAC
    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_LAUNCH_MAIL = 0xB4
    VK_LAUNCH_MEDIA_SELECT = 0xB5
    VK_LAUNCH_APP1 = 0xB6
    VK_LAUNCH_APP2 = 0xB7  # Calculator on most keyboards


# Key name to virtual key code mapping
KEY_NAME_TO_VK: Dict[str, int] = {
    # Letters
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
    'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
    'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
    'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
    'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
    'z': 0x5A,
    # Numbers
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    # Function keys
    'f1': VirtualKey.VK_F1, 'f2': VirtualKey.VK_F2, 'f3': VirtualKey.VK_F3,
    'f4': VirtualKey.VK_F4, 'f5': VirtualKey.VK_F5, 'f6': VirtualKey.VK_F6,
    'f7': VirtualKey.VK_F7, 'f8': VirtualKey.VK_F8, 'f9': VirtualKey.VK_F9,
    'f10': VirtualKey.VK_F10, 'f11': VirtualKey.VK_F11, 'f12': VirtualKey.VK_F12,
    'f13': VirtualKey.VK_F13, 'f14': VirtualKey.VK_F14, 'f15': VirtualKey.VK_F15,
    'f16': VirtualKey.VK_F16, 'f17': VirtualKey.VK_F17, 'f18': VirtualKey.VK_F18,
    'f19': VirtualKey.VK_F19, 'f20': VirtualKey.VK_F20, 'f21': VirtualKey.VK_F21,
    'f22': VirtualKey.VK_F22, 'f23': VirtualKey.VK_F23, 'f24': VirtualKey.VK_F24,
    # Modifiers
    'shift': VirtualKey.VK_SHIFT, 'lshift': VirtualKey.VK_LSHIFT, 'rshift': VirtualKey.VK_RSHIFT,
    'ctrl': VirtualKey.VK_CONTROL, 'lctrl': VirtualKey.VK_LCONTROL, 'rctrl': VirtualKey.VK_RCONTROL,
    'alt': VirtualKey.VK_MENU, 'lalt': VirtualKey.VK_LMENU, 'ralt': VirtualKey.VK_RMENU,
    'win': VirtualKey.VK_LWIN, 'lwin': VirtualKey.VK_LWIN, 'rwin': VirtualKey.VK_RWIN,
    # Special keys
    'escape': VirtualKey.VK_ESCAPE, 'esc': VirtualKey.VK_ESCAPE,
    'tab': VirtualKey.VK_TAB,
    'capslock': VirtualKey.VK_CAPITAL, 'caps': VirtualKey.VK_CAPITAL,
    'space': VirtualKey.VK_SPACE,
    'enter': VirtualKey.VK_RETURN, 'return': VirtualKey.VK_RETURN,
    'backspace': VirtualKey.VK_BACK, 'back': VirtualKey.VK_BACK,
    'delete': VirtualKey.VK_DELETE, 'del': VirtualKey.VK_DELETE,
    'insert': VirtualKey.VK_INSERT, 'ins': VirtualKey.VK_INSERT,
    'home': VirtualKey.VK_HOME,
    'end': VirtualKey.VK_END,
    'pageup': VirtualKey.VK_PRIOR, 'pgup': VirtualKey.VK_PRIOR,
    'pagedown': VirtualKey.VK_NEXT, 'pgdn': VirtualKey.VK_NEXT,
    'printscreen': VirtualKey.VK_SNAPSHOT, 'prtsc': VirtualKey.VK_SNAPSHOT,
    'scrolllock': VirtualKey.VK_SCROLL,
    'pause': VirtualKey.VK_PAUSE,
    'numlock': VirtualKey.VK_NUMLOCK,
    # Arrow keys
    'up': VirtualKey.VK_UP, 'down': VirtualKey.VK_DOWN,
    'left': VirtualKey.VK_LEFT, 'right': VirtualKey.VK_RIGHT,
    # Numpad
    'num0': VirtualKey.VK_NUMPAD0, 'num1': VirtualKey.VK_NUMPAD1,
    'num2': VirtualKey.VK_NUMPAD2, 'num3': VirtualKey.VK_NUMPAD3,
    'num4': VirtualKey.VK_NUMPAD4, 'num5': VirtualKey.VK_NUMPAD5,
    'num6': VirtualKey.VK_NUMPAD6, 'num7': VirtualKey.VK_NUMPAD7,
    'num8': VirtualKey.VK_NUMPAD8, 'num9': VirtualKey.VK_NUMPAD9,
    'numplus': VirtualKey.VK_ADD, 'numminus': VirtualKey.VK_SUBTRACT,
    'nummultiply': VirtualKey.VK_MULTIPLY, 'numdivide': VirtualKey.VK_DIVIDE,
    'numdecimal': VirtualKey.VK_DECIMAL,
    # Punctuation
    'semicolon': VirtualKey.VK_OEM_1, ';': VirtualKey.VK_OEM_1,
    'equals': VirtualKey.VK_OEM_PLUS, '=': VirtualKey.VK_OEM_PLUS,
    'comma': VirtualKey.VK_OEM_COMMA, ',': VirtualKey.VK_OEM_COMMA,
    'minus': VirtualKey.VK_OEM_MINUS, '-': VirtualKey.VK_OEM_MINUS,
    'period': VirtualKey.VK_OEM_PERIOD, '.': VirtualKey.VK_OEM_PERIOD,
    'slash': VirtualKey.VK_OEM_2, '/': VirtualKey.VK_OEM_2,
    'grave': VirtualKey.VK_OEM_3, '`': VirtualKey.VK_OEM_3,
    'lbracket': VirtualKey.VK_OEM_4, '[': VirtualKey.VK_OEM_4,
    'backslash': VirtualKey.VK_OEM_5, '\\': VirtualKey.VK_OEM_5,
    'rbracket': VirtualKey.VK_OEM_6, ']': VirtualKey.VK_OEM_6,
    'quote': VirtualKey.VK_OEM_7, "'": VirtualKey.VK_OEM_7,
    # Context-menu / application key
    'apps': VirtualKey.VK_APPS, 'menu': VirtualKey.VK_APPS,
    # Multimedia
    'mute': VirtualKey.VK_VOLUME_MUTE, 'volumemute': VirtualKey.VK_VOLUME_MUTE,
    'volumedown': VirtualKey.VK_VOLUME_DOWN, 'volumeup': VirtualKey.VK_VOLUME_UP,
    'nexttrack': VirtualKey.VK_MEDIA_NEXT_TRACK, 'prevtrack': VirtualKey.VK_MEDIA_PREV_TRACK,
    'mediastop': VirtualKey.VK_MEDIA_STOP, 'playpause': VirtualKey.VK_MEDIA_PLAY_PAUSE,
    'calculator': VirtualKey.VK_LAUNCH_APP2, 'mail': VirtualKey.VK_LAUNCH_MAIL,
    # Browser
    'browserback': VirtualKey.VK_BROWSER_BACK, 'browserforward': VirtualKey.VK_BROWSER_FORWARD,
    'browserrefresh': VirtualKey.VK_BROWSER_REFRESH, 'browserhome': VirtualKey.VK_BROWSER_HOME,
    'browsersearch': VirtualKey.VK_BROWSER_SEARCH,
    # Mouse buttons usable as a *source* only. Left and right are deliberately
    # absent: remapping them can leave you unable to click your way out.
    'middleclick': VirtualKey.VK_MBUTTON, 'mouse3': VirtualKey.VK_MBUTTON,
    'mouse4': VirtualKey.VK_XBUTTON1, 'mouse5': VirtualKey.VK_XBUTTON2,
}

# Sources handled by the mouse hook rather than the keyboard hook
MOUSE_SOURCE_VKS: Set[int] = {
    int(VirtualKey.VK_MBUTTON), int(VirtualKey.VK_XBUTTON1), int(VirtualKey.VK_XBUTTON2)
}

# Reverse mapping
VK_TO_KEY_NAME: Dict[int, str] = {v: k for k, v in KEY_NAME_TO_VK.items()}

# Modifier virtual keys grouped into "families". The low-level hook reports the
# side-specific code (VK_LSHIFT) while users type the generic name ("shift"), so
# every comparison happens on the family name instead of the raw code.
MODIFIER_FAMILY: Dict[int, str] = {
    int(VirtualKey.VK_SHIFT): 'shift',
    int(VirtualKey.VK_LSHIFT): 'shift',
    int(VirtualKey.VK_RSHIFT): 'shift',
    int(VirtualKey.VK_CONTROL): 'ctrl',
    int(VirtualKey.VK_LCONTROL): 'ctrl',
    int(VirtualKey.VK_RCONTROL): 'ctrl',
    int(VirtualKey.VK_MENU): 'alt',
    int(VirtualKey.VK_LMENU): 'alt',
    int(VirtualKey.VK_RMENU): 'alt',
    int(VirtualKey.VK_LWIN): 'win',
    int(VirtualKey.VK_RWIN): 'win',
}

FAMILY_GENERIC_VK: Dict[str, int] = {
    'shift': int(VirtualKey.VK_SHIFT),
    'ctrl': int(VirtualKey.VK_CONTROL),
    'alt': int(VirtualKey.VK_MENU),
    'win': int(VirtualKey.VK_LWIN),
}

MODIFIER_VKS: Set[int] = set(MODIFIER_FAMILY)

# A combination is matched as (set-of-modifier-families, main key code)
Signature = Tuple[frozenset, int]


def combo_signature(vk_codes: Tuple[int, ...]) -> Signature:
    """Reduce a key combination to a comparable (modifiers, main key) signature."""
    modifiers = [vk for vk in vk_codes if vk in MODIFIER_FAMILY]
    others = [vk for vk in vk_codes if vk not in MODIFIER_FAMILY]

    if others:
        main = others[-1]
        families = {MODIFIER_FAMILY[vk] for vk in modifiers}
    elif modifiers:
        # Modifier-only combo: the last modifier is the trigger key
        main = modifiers[-1]
        families = {MODIFIER_FAMILY[vk] for vk in modifiers[:-1]}
    else:
        raise ValueError("Empty key combination")

    return frozenset(families), main

# Extended keys that require the extended flag
EXTENDED_KEYS = {
    VirtualKey.VK_INSERT, VirtualKey.VK_DELETE, VirtualKey.VK_HOME,
    VirtualKey.VK_END, VirtualKey.VK_PRIOR, VirtualKey.VK_NEXT,
    VirtualKey.VK_LEFT, VirtualKey.VK_RIGHT, VirtualKey.VK_UP, VirtualKey.VK_DOWN,
    VirtualKey.VK_SNAPSHOT, VirtualKey.VK_DIVIDE, VirtualKey.VK_NUMLOCK,
    VirtualKey.VK_RCONTROL, VirtualKey.VK_RMENU,
}


# ULONG_PTR: dwExtraInfo is an opaque integer, NOT a pointer. Declaring it as a
# pointer and dereferencing it faults on events injected by other processes.
ULONG_PTR = ctypes.c_size_t


# Windows structures
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Hook callback types
HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT))
MOUSEHOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(MSLLHOOKSTRUCT))


@dataclass
class KeyMapping:
    """Represents a key mapping configuration"""
    source_keys: Tuple[int, ...]  # Source key(s) - tuple of VK codes
    target_keys: Tuple[int, ...]  # Target key(s) - tuple of VK codes
    enabled: bool = True
    description: str = ""
    # Optional second role: what the key does when held down instead of tapped
    # (e.g. CapsLock -> Escape on tap, Ctrl while held)
    hold_keys: Tuple[int, ...] = ()
    # Executable this rule is limited to, lowercase and without a path
    # ("" = every application)
    app: str = ""


@dataclass
class BlockedKey:
    """Represents a blocked/disabled key"""
    key: Tuple[int, ...]  # Key(s) to block - tuple of VK codes
    enabled: bool = True
    description: str = ""
    app: str = ""


@dataclass
class Settings:
    """Global behaviour switches"""
    toggle_hotkey: str = ""          # e.g. "ctrl+alt+f12" - pauses/resumes everything
    tap_timeout_ms: int = 250        # tap vs hold threshold for dual-role keys
    run_at_startup: bool = False
    start_minimized: bool = False
    start_on_launch: bool = False    # activate the remapper as soon as the app opens


@dataclass
class PendingDualRole:
    """A dual-role key that is down but has not committed to tap or hold yet"""
    mapping: "KeyMapping"
    pressed_at: float
    hold_sent: bool = False


@dataclass
class RemapperState:
    """Tracks the current state of the remapper"""
    active_modifiers: Set[int] = field(default_factory=set)
    pressed_keys: Set[int] = field(default_factory=set)
    # vk -> target keys to release when the physical key comes back up
    # (None when the key was swallowed outright)
    suppressed_keys: Dict[int, Optional[Tuple[int, ...]]] = field(default_factory=dict)
    # vk -> dual-role key waiting to resolve as tap or hold
    pending_dual: Dict[int, PendingDualRole] = field(default_factory=dict)


# --- Copilot key ------------------------------------------------------------
#
# The dedicated "Copilot" key on 2024+ Windows laptops is not a new scan code:
# the firmware emits a chord. On virtually every OEM that chord is
# Left Shift + Left Win + F23, but a few keyboards use Win+C or a bare F23, so
# the chord is stored in the config and can be re-detected per machine.

COPILOT_MODES = ("disable", "keys", "launch", "url", "passthrough")

DEFAULT_COPILOT_MODIFIERS: Tuple[str, ...] = ('shift', 'win')
DEFAULT_COPILOT_KEY = int(VirtualKey.VK_F23)


@dataclass
class CopilotConfig:
    """What the OEM Copilot key should do."""
    enabled: bool = False
    modifiers: Tuple[str, ...] = DEFAULT_COPILOT_MODIFIERS  # families: shift/ctrl/alt/win
    key: int = DEFAULT_COPILOT_KEY
    mode: str = "disable"      # one of COPILOT_MODES
    value: str = ""            # key combo / program path / URL, depending on mode
    description: str = ""

    @property
    def signature(self) -> Signature:
        return frozenset(self.modifiers), self.key

    def chord_text(self) -> str:
        """Human readable chord, e.g. 'SHIFT+WIN+F23'."""
        order = {'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3}
        parts = sorted(self.modifiers, key=lambda m: order.get(m, 9))
        parts.append(VK_TO_KEY_NAME.get(self.key, f"0x{self.key:02X}"))
        return '+'.join(p.upper() for p in parts)

    def action_text(self) -> str:
        if self.mode == "disable":
            return "Do nothing (key disabled)"
        if self.mode == "keys":
            return f"Send keys: {self.value}"
        if self.mode == "launch":
            return f"Launch: {self.value}"
        if self.mode == "url":
            return f"Open URL: {self.value}"
        return "Pass through (unchanged)"


def settings_from_dict(data: Optional[Dict]) -> Settings:
    """Build a Settings from saved JSON, tolerating missing/old fields."""
    if not isinstance(data, dict):
        return Settings()

    defaults = Settings()
    try:
        tap_timeout = int(data.get("tap_timeout_ms", defaults.tap_timeout_ms))
    except (TypeError, ValueError):
        tap_timeout = defaults.tap_timeout_ms

    return Settings(
        toggle_hotkey=str(data.get("toggle_hotkey", "")),
        tap_timeout_ms=max(50, min(2000, tap_timeout)),
        run_at_startup=bool(data.get("run_at_startup", False)),
        start_minimized=bool(data.get("start_minimized", False)),
        start_on_launch=bool(data.get("start_on_launch", False)),
    )


def copilot_from_dict(data: Optional[Dict]) -> CopilotConfig:
    """Build a CopilotConfig from saved JSON, tolerating missing/old fields."""
    if not isinstance(data, dict):
        return CopilotConfig()

    raw_key = data.get("key", DEFAULT_COPILOT_KEY)
    if isinstance(raw_key, str):
        key = int(KEY_NAME_TO_VK.get(raw_key.lower().strip(), DEFAULT_COPILOT_KEY))
    else:
        try:
            key = int(raw_key)
        except (TypeError, ValueError):
            key = DEFAULT_COPILOT_KEY

    modifiers = tuple(
        m for m in data.get("modifiers", DEFAULT_COPILOT_MODIFIERS)
        if m in FAMILY_GENERIC_VK
    )

    mode = data.get("mode", "disable")
    if mode not in COPILOT_MODES:
        mode = "disable"

    return CopilotConfig(
        enabled=bool(data.get("enabled", False)),
        modifiers=modifiers,
        key=key,
        mode=mode,
        value=str(data.get("value", "")),
        description=str(data.get("description", "")),
    )


class KeyRemapper:
    """
    Low-level Windows key remapper with gaming support.
    Uses Windows hooks for maximum compatibility with games and applications.
    """
    
    def __init__(self):
        # Rules are keyed by (source keys, app) so the same key can behave
        # differently per application
        self.mappings: Dict[Tuple[Tuple[int, ...], str], KeyMapping] = {}
        self.blocked_keys: Dict[Tuple[Tuple[int, ...], str], BlockedKey] = {}
        self.copilot = CopilotConfig()
        self.settings = Settings()
        self.state = RemapperState()
        self.hook_handle = None
        self.hook_callback = None
        self.mouse_hook_handle = None
        self.mouse_hook_callback = None
        self.running = False
        self.paused = False
        self.message_thread = None
        self._lock = threading.Lock()

        # Normalized lookup tables, rebuilt whenever mappings/blocks change
        self._mapping_index: Dict[Tuple[Signature, str], KeyMapping] = {}
        self._blocked_index: Dict[Tuple[Signature, str], BlockedKey] = {}
        self._copilot_target: Tuple[int, ...] = ()
        self._toggle_signature: Optional[Signature] = None
        self._has_app_rules = False
        self._needs_mouse_hook = False

        # Foreground executable cache (the hook must stay fast)
        self._fg_exe = ""
        self._fg_checked = 0.0
        self._fg_hwnd = None

        # Hook lifecycle
        self._message_thread_id = None
        self._hook_ready = threading.Event()
        self._hook_installed = False

        # Chord capture (used by "detect my Copilot key")
        self._capture_callback: Optional[Callable] = None
        self._capture_drain = False
        self._capture_started_hook = False

        # Slow actions (launching apps, opening URLs) must never run inside the
        # hook callback: Windows silently drops hooks that take too long.
        self._action_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self._action_thread: Optional[threading.Thread] = None

        # Notified (from the hook thread) whenever pause state flips
        self.on_pause_changed: Optional[Callable[[bool], None]] = None

        # Marker to identify our own injected events
        self._injection_marker = 0xDEADBEEF

        # Register cleanup on exit
        atexit.register(self.stop)

    # ------------------------------------------------------------------
    # Lookup index
    # ------------------------------------------------------------------

    def _rebuild_index(self):
        """Rebuild the normalized signature lookup tables. Caller holds the lock."""
        self._mapping_index = {}
        for (keys, app), mapping in self.mappings.items():
            try:
                self._mapping_index[(combo_signature(keys), app)] = mapping
            except ValueError:
                continue

        self._blocked_index = {}
        for (keys, app), blocked in self.blocked_keys.items():
            try:
                self._blocked_index[(combo_signature(keys), app)] = blocked
            except ValueError:
                continue

        self._has_app_rules = any(app for _, app in self.mappings) or \
            any(app for _, app in self.blocked_keys)

        rule_keys = [keys for keys, _ in self.mappings] + [keys for keys, _ in self.blocked_keys]
        self._needs_mouse_hook = any(
            vk in MOUSE_SOURCE_VKS for keys in rule_keys for vk in keys
        )

    def _lookup(self, index: Dict, families: frozenset, vk: int, app: str):
        """
        Find a rule for the pressed key.

        Tries the app-specific rule first, then the global one, and falls back
        to the generic modifier code (the hook reports VK_LSHIFT, users type
        "shift").
        """
        candidates = [vk]
        family = MODIFIER_FAMILY.get(vk)
        if family:
            candidates.append(FAMILY_GENERIC_VK[family])

        for scope in ((app, "") if app else ("",)):
            for candidate in candidates:
                entry = index.get(((families, candidate), scope))
                if entry is not None:
                    return entry
        return None

    # ------------------------------------------------------------------
    # Foreground application (per-app profiles)
    # ------------------------------------------------------------------

    def _foreground_exe(self) -> str:
        """
        Executable name of the focused window, lowercased.

        Cached for a fifth of a second: this runs inside the hook and the answer
        cannot change between two keystrokes of the same burst anyway.
        """
        if not self._has_app_rules:
            return ""

        now = time.monotonic()
        hwnd = user32.GetForegroundWindow()
        if hwnd == self._fg_hwnd and (now - self._fg_checked) < 0.2:
            return self._fg_exe

        self._fg_hwnd = hwnd
        self._fg_checked = now
        self._fg_exe = ""

        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""

            # PROCESS_QUERY_LIMITED_INFORMATION works without elevation
            handle = kernel32.OpenProcess(0x1000, False, pid.value)
            if not handle:
                return ""
            try:
                buffer = ctypes.create_unicode_buffer(520)
                size = wintypes.DWORD(len(buffer))
                if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    self._fg_exe = os.path.basename(buffer.value).lower()
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            logger.debug("Could not resolve foreground process", exc_info=True)

        return self._fg_exe

    def parse_key_string(self, key_string: str) -> Tuple[int, ...]:
        """
        Parse a key string like 'ctrl+shift+a' into a tuple of VK codes.

        Args:
            key_string: Key combination string (e.g., 'ctrl+a', 'f1', 'shift+f5')

        Returns:
            Tuple of virtual key codes

        Raises:
            ValueError: If key name is not recognized
        """
        keys = []
        parts = key_string.lower().strip().split('+')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if part in KEY_NAME_TO_VK:
                keys.append(KEY_NAME_TO_VK[part])
            else:
                raise ValueError(f"Unknown key: '{part}'. Use 'list' command to see available keys.")

        if not keys:
            raise ValueError("No valid keys specified")

        # Sort modifiers first for consistent ordering
        modifiers = sorted([k for k in keys if k in MODIFIER_VKS])
        non_modifiers = [k for k in keys if k not in MODIFIER_VKS]

        return tuple(modifiers + non_modifiers)

    def vk_to_string(self, vk_codes: Tuple[int, ...]) -> str:
        """Convert VK codes back to a readable string"""
        names = []
        for vk in vk_codes:
            name = VK_TO_KEY_NAME.get(vk, f"0x{vk:02X}")
            names.append(name.upper())
        return '+'.join(names)

    @staticmethod
    def normalize_app(app: str) -> str:
        """Reduce an app filter to a bare lowercase executable name"""
        app = (app or "").strip().strip('"')
        if not app:
            return ""
        return os.path.basename(app).lower()

    def find_conflict(self, source: str, app: str = "", ignore: Tuple = None) -> Optional[str]:
        """
        Describe an existing rule that would collide with ``source``.

        Returns None when the combination is free.
        """
        try:
            keys = self.parse_key_string(source)
            signature = combo_signature(keys)
        except ValueError:
            return None

        app = self.normalize_app(app)
        scope = f" in {app}" if app else ""

        with self._lock:
            for (rule_keys, rule_app), mapping in self.mappings.items():
                if (rule_keys, rule_app) == ignore:
                    continue
                if rule_app == app and combo_signature(rule_keys) == signature:
                    return (f"{self.vk_to_string(rule_keys)}{scope} is already remapped to "
                            f"{self.vk_to_string(mapping.target_keys)}")

            for (rule_keys, rule_app), _ in self.blocked_keys.items():
                if (rule_keys, rule_app) == ignore:
                    continue
                if rule_app == app and combo_signature(rule_keys) == signature:
                    return f"{self.vk_to_string(rule_keys)}{scope} is already blocked"

        return None

    def add_mapping(self, source: str, target: str, description: str = "",
                    hold: str = "", app: str = "") -> bool:
        """
        Add a key mapping.

        Args:
            source: Source key(s) string (e.g., 'capslock', 'ctrl+a')
            target: Target key(s) string (e.g., 'escape', 'ctrl+c')
            description: Optional description
            hold: Optional second role - what the key does when held down
            app: Optional executable this mapping is limited to

        Returns:
            True if mapping was added successfully
        """
        try:
            source_keys = self.parse_key_string(source)
            target_keys = self.parse_key_string(target)
            hold_keys = self.parse_key_string(hold) if hold.strip() else ()
            app = self.normalize_app(app)

            if hold_keys and len(source_keys) > 1:
                logger.warning("Hold actions only work on single keys, not combinations")
                return False

            # Mouse buttons are read from the mouse hook; SendInput cannot press
            # them as keyboard events, so they are sources only
            if any(vk in MOUSE_SOURCE_VKS for vk in target_keys + hold_keys):
                logger.warning("Mouse buttons can only be used as a source, not a target")
                return False

            mapping = KeyMapping(
                source_keys=source_keys,
                target_keys=target_keys,
                enabled=True,
                description=description or f"{source} -> {target}",
                hold_keys=hold_keys,
                app=app,
            )

            with self._lock:
                self.mappings[(source_keys, app)] = mapping
                self._rebuild_index()

            logger.info("Added mapping: %s -> %s%s%s", source, target,
                        f" (hold: {hold})" if hold_keys else "",
                        f" [{app}]" if app else "")
            return True

        except ValueError as exc:
            logger.warning("Could not add mapping %r -> %r: %s", source, target, exc)
            return False

    def remove_mapping(self, source: str, app: str = "") -> bool:
        """Remove a key mapping by source key string"""
        try:
            source_keys = self.parse_key_string(source)
            key = (source_keys, self.normalize_app(app))

            with self._lock:
                if key in self.mappings:
                    del self.mappings[key]
                    self._rebuild_index()
                    logger.info("Removed mapping: %s", source)
                    return True
                else:
                    return False

        except ValueError:
            return False

    def toggle_mapping(self, source: str, app: str = "") -> bool:
        """Toggle a mapping on/off"""
        try:
            key = (self.parse_key_string(source), self.normalize_app(app))

            with self._lock:
                if key in self.mappings:
                    self.mappings[key].enabled = not self.mappings[key].enabled
                    return True
                return False

        except ValueError:
            return False

    def block_key(self, key: str, description: str = "", app: str = "") -> bool:
        """
        Block/disable a key completely (key press will be ignored).

        Args:
            key: Key(s) string to block (e.g., '/', 'ctrl+/', 'f1')
            description: Optional description
            app: Optional executable this block is limited to

        Returns:
            True if key was blocked successfully
        """
        try:
            key_codes = self.parse_key_string(key)
            app = self.normalize_app(app)

            blocked = BlockedKey(
                key=key_codes,
                enabled=True,
                description=description or f"Block {key}",
                app=app,
            )

            with self._lock:
                self.blocked_keys[(key_codes, app)] = blocked
                self._rebuild_index()

            logger.info("Blocked key: %s%s", key, f" [{app}]" if app else "")
            return True

        except ValueError as exc:
            logger.warning("Could not block %r: %s", key, exc)
            return False

    def unblock_key(self, key: str, app: str = "") -> bool:
        """Unblock a previously blocked key"""
        try:
            index_key = (self.parse_key_string(key), self.normalize_app(app))

            with self._lock:
                if index_key in self.blocked_keys:
                    del self.blocked_keys[index_key]
                    self._rebuild_index()
                    logger.info("Unblocked key: %s", key)
                    return True
                else:
                    return False

        except ValueError:
            return False

    def toggle_blocked_key(self, key: str, app: str = "") -> bool:
        """Toggle a blocked key on/off"""
        try:
            index_key = (self.parse_key_string(key), self.normalize_app(app))

            with self._lock:
                if index_key in self.blocked_keys:
                    self.blocked_keys[index_key].enabled = not self.blocked_keys[index_key].enabled
                    return True
                return False

        except ValueError:
            return False

    def list_blocked_keys(self) -> List[Dict]:
        """Get a list of all blocked keys"""
        result = []
        with self._lock:
            for blocked in self.blocked_keys.values():
                result.append({
                    "key": self.vk_to_string(blocked.key),
                    "enabled": blocked.enabled,
                    "description": blocked.description,
                    "app": blocked.app,
                })
        return result

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def apply_settings(self, settings: Settings) -> bool:
        """Install global settings. Returns False if the toggle hotkey is invalid."""
        signature = None
        hotkey = settings.toggle_hotkey.strip()
        if hotkey:
            try:
                signature = combo_signature(self.parse_key_string(hotkey))
            except ValueError as exc:
                logger.warning("Invalid toggle hotkey %r: %s", hotkey, exc)
                return False

        with self._lock:
            self.settings = settings
            self._toggle_signature = signature

        logger.info("Settings applied (toggle hotkey: %s)", hotkey or "none")
        return True

    def _release_held_targets(self):
        """Release anything we are currently holding down on the user's behalf."""
        for target in self.state.suppressed_keys.values():
            if target:
                self._send_key_combination(target, key_up=True)
        self.state.suppressed_keys.clear()

        for pending in self.state.pending_dual.values():
            if pending.hold_sent:
                self._send_key_combination(pending.mapping.hold_keys, key_up=True)
        self.state.pending_dual.clear()

    def set_paused(self, paused: bool):
        """Pause or resume all remapping without releasing the hook"""
        if self.paused == paused:
            return
        self.paused = paused
        # Never leave an injected key stuck down across a pause
        self._release_held_targets()
        logger.info("Remapper %s", "paused" if paused else "resumed")
        if self.on_pause_changed:
            try:
                self.on_pause_changed(paused)
            except Exception:
                logger.exception("Pause callback failed")

    def _send_key(self, vk_code: int, key_up: bool = False):
        """Send a single key event using SendInput"""
        flags = 0
        if key_up:
            flags |= KEYEVENTF_KEYUP
        if vk_code in EXTENDED_KEYS:
            flags |= KEYEVENTF_EXTENDEDKEY
        
        # Get scan code
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk_code
        inp.union.ki.wScan = scan_code
        inp.union.ki.dwFlags = flags
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = self._injection_marker
        
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    
    def _send_key_combination(self, vk_codes: Tuple[int, ...], key_up: bool = False):
        """Send a key combination"""
        if key_up:
            # Release in reverse order
            for vk in reversed(vk_codes):
                self._send_key(vk, key_up=True)
        else:
            # Press in order
            for vk in vk_codes:
                self._send_key(vk, key_up=False)
    
    def _send_dummy_key(self):
        """
        Press an unassigned virtual key.

        When we swallow a key that was pressed while Windows is held down, the
        OS never sees a "real" key in between and pops the Start menu on the Win
        release. Injecting an unassigned key marks the Win press as consumed.
        """
        self._send_key(DUMMY_KEY, key_up=False)
        self._send_key(DUMMY_KEY, key_up=True)

    def _release_physical_modifiers(self):
        """Virtually release modifiers the user is physically holding.

        Needed before injecting a replacement combination, otherwise the held
        Shift/Win of the original chord leaks into the keys we send.
        """
        for vk in sorted(self.state.active_modifiers):
            self._send_key(vk, key_up=True)

    def _is_injected(self, kb_struct: KBDLLHOOKSTRUCT) -> bool:
        """Check if the event was injected by us"""
        if kb_struct.flags & LLKHF_INJECTED:
            return kb_struct.dwExtraInfo == self._injection_marker
        return False

    # ------------------------------------------------------------------
    # Copilot key
    # ------------------------------------------------------------------

    def set_copilot(self, config: CopilotConfig) -> bool:
        """Install a Copilot key configuration. Returns False if it is invalid."""
        if config.mode not in COPILOT_MODES:
            logger.warning("Unknown Copilot mode: %s", config.mode)
            return False

        target: Tuple[int, ...] = ()
        if config.mode == "keys":
            try:
                target = self.parse_key_string(config.value)
            except ValueError as exc:
                logger.warning("Invalid Copilot target keys %r: %s", config.value, exc)
                return False
        elif config.mode in ("launch", "url") and not config.value.strip():
            logger.warning("Copilot mode %s needs a value", config.mode)
            return False

        with self._lock:
            self.copilot = config
            self._copilot_target = target

        logger.info("Copilot key %s: %s -> %s",
                    "enabled" if config.enabled else "disabled",
                    config.chord_text(), config.action_text())
        return True

    def _copilot_matches(self, vk_code: int, families: frozenset) -> bool:
        copilot = self.copilot
        if not copilot.enabled or copilot.mode == "passthrough":
            return False
        return vk_code == copilot.key and families == frozenset(copilot.modifiers)

    def _copilot_is_modifier_target(self) -> bool:
        """True when the Copilot key stands in for a modifier-only key."""
        target = self._copilot_target
        return bool(target) and all(
            vk in MODIFIER_VKS or vk == int(VirtualKey.VK_APPS) for vk in target
        )

    def _trigger_copilot(self, families: frozenset) -> Tuple[int, ...]:
        """
        Run the configured Copilot action. Must stay fast - we are in the hook.

        Returns the keys that are now held down and must be released when the
        Copilot key comes back up (empty for one-shot actions).
        """
        copilot = self.copilot

        # Keep the Start menu from appearing when the held Win key is released
        if 'win' in families:
            self._send_dummy_key()

        if copilot.mode == "disable":
            return ()

        if copilot.mode == "keys":
            target = self._copilot_target
            if target:
                self._release_physical_modifiers()
                self._send_key_combination(target, key_up=False)
                if self._copilot_is_modifier_target():
                    # Stand-in for Right Alt / Menu / Right Ctrl and friends:
                    # mirror the physical key so holding it holds the modifier.
                    # (Most firmware releases the chord immediately, which then
                    # behaves as a tap - the useful result either way.)
                    return target
                self._send_key_combination(target, key_up=True)
        elif copilot.mode in ("launch", "url"):
            self._release_physical_modifiers()
            self._ensure_action_worker()
            self._action_queue.put((copilot.mode, copilot.value))

        return ()

    def _ensure_action_worker(self):
        if self._action_thread and self._action_thread.is_alive():
            return
        self._action_thread = threading.Thread(
            target=self._action_worker, name="KeyRemapperActions", daemon=True
        )
        self._action_thread.start()

    def _action_worker(self):
        """Runs launch/open actions off the hook thread."""
        while True:
            mode, value = self._action_queue.get()
            try:
                if mode == "url":
                    url = value.strip()
                    if not url.startswith(("http://", "https://", "ms-", "file:")):
                        url = "https://" + url
                    webbrowser.open(url)
                    logger.info("Copilot key opened URL: %s", url)
                elif mode == "launch":
                    self._launch(value)
            except Exception:
                logger.exception("Copilot action failed: %s %r", mode, value)

    @staticmethod
    def _launch(command: str):
        """Start a program, document or folder."""
        target = command.strip().strip('"')
        if os.path.exists(target):
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            # Allows "notepad", "shell:AppsFolder\\..." and commands with arguments
            subprocess.Popen(command, shell=True)
        logger.info("Copilot key launched: %s", command)

    # ------------------------------------------------------------------
    # Chord capture ("what does my Copilot key actually send?")
    # ------------------------------------------------------------------

    def start_capture(self, callback: Callable[[Optional[Tuple[Tuple[str, ...], int]]], None]) -> bool:
        """
        Swallow all keyboard input until one chord is pressed, then report it.

        The callback receives ``(modifier_families, vk_code)`` or ``None`` if the
        user pressed Escape to cancel. It runs on the hook thread, so GUI code
        must marshal back to its own thread.
        """
        if self._capture_callback is not None:
            return False

        self._capture_started_hook = not self.running
        if not self.running and not self.start():
            return False

        self._capture_callback = callback
        logger.info("Chord capture started")
        return True

    def cancel_capture(self):
        """Abort an in-progress capture without reporting a chord."""
        if self._capture_callback is not None:
            self._finish_capture(None)

    def run_copilot_action(self):
        """Run the configured Copilot action right now (used by the Test button)."""
        self._trigger_copilot(frozenset())

    def _finish_capture(self, chord):
        callback = self._capture_callback
        self._capture_callback = None
        self._capture_drain = True

        if self._capture_started_hook:
            self._capture_started_hook = False
            # Stopping the hook from inside its own callback would deadlock
            threading.Thread(target=self.stop, daemon=True).start()

        if callback:
            try:
                callback(chord)
            except Exception:
                logger.exception("Capture callback failed")

    def _handle_capture(self, vk_code: int, is_keydown: bool, family: Optional[str]) -> int:
        if is_keydown:
            if vk_code == int(VirtualKey.VK_ESCAPE) and not self.state.active_modifiers:
                logger.info("Chord capture cancelled")
                self._finish_capture(None)
            elif family is None:
                families = tuple(sorted(
                    MODIFIER_FAMILY[m] for m in self.state.active_modifiers
                ))
                logger.info("Chord captured: %s + 0x%02X", families, vk_code)
                self._finish_capture((families, vk_code))
        return 1  # swallow everything while capturing

    # ------------------------------------------------------------------
    # Dual-role (tap vs hold) keys
    # ------------------------------------------------------------------

    def _start_dual_role(self, vk_code: int, mapping: KeyMapping) -> int:
        """A dual-role key went down: emit nothing yet, wait for tap or hold."""
        if vk_code in self.state.pending_dual:
            return 1  # auto-repeat while held - still undecided
        self.state.pending_dual[vk_code] = PendingDualRole(
            mapping=mapping, pressed_at=time.monotonic()
        )
        return 1

    def _commit_dual_holds(self):
        """
        Another key was pressed while a dual-role key was down, so the
        dual-role key is being used as a modifier: send its hold role now.
        """
        for pending in self.state.pending_dual.values():
            if not pending.hold_sent:
                pending.hold_sent = True
                self._send_key_combination(pending.mapping.hold_keys, key_up=False)

    def _resolve_dual_role(self, vk_code: int) -> int:
        """The dual-role key came back up: decide between tap and hold."""
        pending = self.state.pending_dual.pop(vk_code, None)
        if pending is None:
            return 0

        if pending.hold_sent:
            self._send_key_combination(pending.mapping.hold_keys, key_up=True)
        else:
            held_ms = (time.monotonic() - pending.pressed_at) * 1000
            if held_ms <= self.settings.tap_timeout_ms:
                self._send_key_combination(pending.mapping.target_keys, key_up=False)
                self._send_key_combination(pending.mapping.target_keys, key_up=True)
            else:
                # Held on its own for a long time and never used as a modifier:
                # emit the hold role as a press so the key is never a no-op.
                self._send_key_combination(pending.mapping.hold_keys, key_up=False)
                self._send_key_combination(pending.mapping.hold_keys, key_up=True)
        return 1

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    def _handle_key_event(self, vk_code: int, is_keydown: bool, is_keyup: bool) -> bool:
        """
        Shared keyboard/mouse rule engine.

        Returns True when the event should be swallowed.
        """
        family = MODIFIER_FAMILY.get(vk_code)

        # Track physical key state
        if is_keydown:
            self.state.pressed_keys.add(vk_code)
            if family:
                self.state.active_modifiers.add(vk_code)
        elif is_keyup:
            self.state.pressed_keys.discard(vk_code)
            if family:
                self.state.active_modifiers.discard(vk_code)

        if self._capture_callback is not None:
            self._handle_capture(vk_code, is_keydown, family)
            return True

        if self._capture_drain:
            # Swallow the tail of the captured chord (e.g. the Win/Shift
            # releases) so it cannot leak into the desktop
            if not self.state.pressed_keys:
                self._capture_drain = False
            return True

        # Modifier families currently held, excluding the key itself
        families = frozenset(
            MODIFIER_FAMILY[m] for m in self.state.active_modifiers if m != vk_code
        )

        # Pause / resume hotkey - handled even while paused
        if self._toggle_signature is not None:
            if is_keydown and (families, vk_code) == self._toggle_signature:
                self.set_paused(not self.paused)
                self.state.suppressed_keys[vk_code] = None
                return True

        # Release of a key we swallowed on the way down. This runs before the
        # pause check so a key held across a pause still gets its release.
        if is_keyup:
            if self._resolve_dual_role(vk_code):
                return True
            if vk_code in self.state.suppressed_keys:
                target = self.state.suppressed_keys.pop(vk_code)
                if target:
                    self._send_key_combination(target, key_up=True)
                return True
            return False

        if self.paused or not is_keydown:
            return False

        # A real key press means any pending dual-role key is acting as a modifier
        if self.state.pending_dual and vk_code not in self.state.pending_dual:
            self._commit_dual_holds()

        # 1. Copilot key
        if self._copilot_matches(vk_code, families):
            self.state.suppressed_keys[vk_code] = self._trigger_copilot(families)
            return True

        app = self._foreground_exe()

        with self._lock:
            blocked = self._lookup(self._blocked_index, families, vk_code, app)
            mapping = self._lookup(self._mapping_index, families, vk_code, app)

        # 2. Blocked keys
        if blocked is not None and blocked.enabled:
            self.state.suppressed_keys[vk_code] = None
            return True

        # 3. Remapped keys
        if mapping is not None and mapping.enabled:
            if mapping.hold_keys:
                return bool(self._start_dual_role(vk_code, mapping))
            self.state.suppressed_keys[vk_code] = mapping.target_keys
            self._send_key_combination(mapping.target_keys, key_up=False)
            return True

        return False

    def _keyboard_callback(self, nCode: int, wParam, lParam) -> int:
        """Low-level keyboard hook callback (runs on the message-loop thread)"""
        if nCode < 0:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        try:
            kb = lParam.contents

            # Skip our own injected events
            if self._is_injected(kb):
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            if self._handle_key_event(
                kb.vkCode,
                wParam in (WM_KEYDOWN, WM_SYSKEYDOWN),
                wParam in (WM_KEYUP, WM_SYSKEYUP),
            ):
                return 1

        except Exception:
            logger.exception("Error in keyboard hook")

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _mouse_callback(self, nCode: int, wParam, lParam) -> int:
        """
        Low-level mouse hook callback.

        Only the middle and side buttons are considered - remapping left/right
        could leave the user unable to click their way back out.
        """
        if nCode < 0 or wParam == WM_MOUSEMOVE:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        try:
            if wParam not in (WM_MBUTTONDOWN, WM_MBUTTONUP, WM_XBUTTONDOWN, WM_XBUTTONUP):
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            ms = lParam.contents
            if ms.flags & LLKHF_INJECTED and ms.dwExtraInfo == self._injection_marker:
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            if wParam in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                vk_code = int(VirtualKey.VK_MBUTTON)
            else:
                which = (ms.mouseData >> 16) & 0xFFFF
                vk_code = int(VirtualKey.VK_XBUTTON1 if which == XBUTTON1
                              else VirtualKey.VK_XBUTTON2)

            if self._handle_key_event(
                vk_code,
                wParam in (WM_MBUTTONDOWN, WM_XBUTTONDOWN),
                wParam in (WM_MBUTTONUP, WM_XBUTTONUP),
            ):
                return 1

        except Exception:
            logger.exception("Error in mouse hook")

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _message_loop(self):
        """
        Own the hooks from a dedicated thread.

        A WH_KEYBOARD_LL hook is dispatched on the thread that installed it, and
        that thread must pump messages. Installing it here keeps the hook alive
        regardless of what the GUI (or a blocking CLI prompt) is doing.
        """
        self._message_thread_id = kernel32.GetCurrentThreadId()

        try:
            self.hook_callback = HOOKPROC(self._keyboard_callback)
            self.hook_handle = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self.hook_callback, None, 0
            )
            self._hook_installed = bool(self.hook_handle)
            if not self._hook_installed:
                logger.error("SetWindowsHookEx failed (error %s)", ctypes.get_last_error())

            # The mouse hook sees every movement, so only install it when a rule
            # actually uses a mouse button
            if self._hook_installed and self._needs_mouse_hook:
                self.mouse_hook_callback = MOUSEHOOKPROC(self._mouse_callback)
                self.mouse_hook_handle = user32.SetWindowsHookExW(
                    WH_MOUSE_LL, self.mouse_hook_callback, None, 0
                )
                if not self.mouse_hook_handle:
                    logger.error("Mouse hook failed (error %s)", ctypes.get_last_error())
        finally:
            self._hook_ready.set()

        if not self._hook_installed:
            return

        msg = wintypes.MSG()
        while self.running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self.mouse_hook_handle:
            user32.UnhookWindowsHookEx(self.mouse_hook_handle)
            self.mouse_hook_handle = None
        self.mouse_hook_callback = None

        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None
        self.hook_callback = None
        logger.info("Keyboard hook released")

    def start(self) -> bool:
        """Start the key remapper"""
        if self.running:
            return False

        self.running = True
        self.paused = False
        self._hook_ready.clear()
        self._hook_installed = False
        self.state = RemapperState()

        self.message_thread = threading.Thread(
            target=self._message_loop, name="KeyRemapperHook", daemon=True
        )
        self.message_thread.start()

        # Wait for the hook to be installed so callers get a real result
        if not self._hook_ready.wait(timeout=5.0) or not self._hook_installed:
            self.running = False
            logger.error("Key remapper failed to start")
            return False

        logger.info("Key remapper started successfully")
        return True

    def stop(self):
        """Stop the key remapper"""
        if not self.running:
            return

        self.running = False
        self.paused = False
        self._capture_callback = None
        self._capture_drain = False

        try:
            self._release_held_targets()
        except Exception:
            logger.debug("Could not release held keys on stop", exc_info=True)

        # Wake the message loop so it can unhook on its own thread
        if self._message_thread_id:
            user32.PostThreadMessageW(
                self._message_thread_id,
                0x0012,  # WM_QUIT
                0, 0
            )
            self._message_thread_id = None

        thread = self.message_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self.message_thread = None

        self.state = RemapperState()
        logger.info("Key remapper stopped")

    def save_config(self, filepath: Path = None) -> bool:
        """Save current mappings, blocked keys and Copilot setup to a JSON file"""
        filepath = Path(filepath) if filepath else CONFIG_FILE
        try:
            copilot = self.copilot
            settings = self.settings
            config = {
                "version": 4,
                "mappings": [
                    {
                        "source": self.vk_to_string(m.source_keys),
                        "target": self.vk_to_string(m.target_keys),
                        "hold": self.vk_to_string(m.hold_keys) if m.hold_keys else "",
                        "app": m.app,
                        "enabled": m.enabled,
                        "description": m.description
                    }
                    for m in self.mappings.values()
                ],
                "blocked_keys": [
                    {
                        "key": self.vk_to_string(b.key),
                        "app": b.app,
                        "enabled": b.enabled,
                        "description": b.description
                    }
                    for b in self.blocked_keys.values()
                ],
                "settings": {
                    "toggle_hotkey": settings.toggle_hotkey,
                    "tap_timeout_ms": settings.tap_timeout_ms,
                    "run_at_startup": settings.run_at_startup,
                    "start_minimized": settings.start_minimized,
                    "start_on_launch": settings.start_on_launch,
                },
                "copilot": {
                    "enabled": copilot.enabled,
                    "modifiers": list(copilot.modifiers),
                    "key": VK_TO_KEY_NAME.get(copilot.key, copilot.key),
                    "mode": copilot.mode,
                    "value": copilot.value,
                    "description": copilot.description
                }
            }

            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)

            return True

        except OSError:
            logger.exception("Failed to save config to %s", filepath)
            return False

    def load_config(self, filepath: Path = None) -> bool:
        """Load mappings, blocked keys and Copilot setup from a JSON file"""
        if filepath is None:
            filepath = CONFIG_FILE
            # One-time migration from the old "next to the script" location
            if not filepath.exists() and LEGACY_CONFIG_FILE.exists():
                logger.info("Migrating config from %s", LEGACY_CONFIG_FILE)
                filepath = LEGACY_CONFIG_FILE
        filepath = Path(filepath)

        try:
            if not filepath.exists():
                logger.info("No config file found at %s", filepath)
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)

            with self._lock:
                self.mappings.clear()
                self.blocked_keys.clear()
                self._rebuild_index()

            # Load mappings
            for mapping_data in config.get("mappings", []):
                source = mapping_data.get("source", "")
                target = mapping_data.get("target", "")
                description = mapping_data.get("description", "")
                hold = mapping_data.get("hold", "")
                app = mapping_data.get("app", "")

                if source and target:
                    self.add_mapping(source, target, description, hold=hold, app=app)

                    # Handle enabled state
                    if not mapping_data.get("enabled", True):
                        self.toggle_mapping(source, app)

            # Load blocked keys
            for blocked_data in config.get("blocked_keys", []):
                key = blocked_data.get("key", "")
                description = blocked_data.get("description", "")
                app = blocked_data.get("app", "")

                if key:
                    self.block_key(key, description, app=app)

                    # Handle enabled state
                    if not blocked_data.get("enabled", True):
                        self.toggle_blocked_key(key, app)

            # Load Copilot key setup
            self.set_copilot(copilot_from_dict(config.get("copilot")))

            # Load global settings
            self.apply_settings(settings_from_dict(config.get("settings")))

            logger.info("Loaded config from %s", filepath)
            return True

        except (OSError, ValueError):
            logger.exception("Failed to load config from %s", filepath)
            return False

    def list_mappings(self) -> List[Dict]:
        """Get a list of all current mappings"""
        result = []
        with self._lock:
            for mapping in self.mappings.values():
                result.append({
                    "source": self.vk_to_string(mapping.source_keys),
                    "target": self.vk_to_string(mapping.target_keys),
                    "hold": self.vk_to_string(mapping.hold_keys) if mapping.hold_keys else "",
                    "app": mapping.app,
                    "enabled": mapping.enabled,
                    "description": mapping.description
                })
        return result


STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command(minimized: bool = True) -> str:
    """The command Windows should run at logon."""
    if getattr(sys, 'frozen', False):
        command = f'"{sys.executable}"'
    else:
        gui = Path(__file__).parent / "key_remapper_gui.py"
        command = f'"{sys.executable}" "{gui}"'
    return f"{command} --minimized" if minimized else command


def set_run_at_startup(enabled: bool, minimized: bool = True) -> bool:
    """Add or remove the logon entry under HKCU (no elevation needed)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                                  startup_command(minimized))
                logger.info("Run at startup enabled")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    logger.info("Run at startup disabled")
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        logger.exception("Could not update the run-at-startup entry")
        return False


def is_run_at_startup() -> bool:
    """Whether the logon entry currently exists."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except OSError:
        return False


def check_admin() -> bool:
    """
    Check if running with administrator privileges.

    Informational only: the remapper works fine unelevated. Elevation is only
    needed to affect windows that themselves run elevated.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def print_available_keys():
    """Print all available key names"""
    print("\n=== Available Key Names ===\n")
    
    categories = {
        "Letters": [k for k in KEY_NAME_TO_VK.keys() if len(k) == 1 and k.isalpha()],
        "Numbers": [k for k in KEY_NAME_TO_VK.keys() if len(k) == 1 and k.isdigit()],
        "Function Keys": [k for k in KEY_NAME_TO_VK.keys() if k.startswith('f') and k[1:].isdigit()],
        "Modifiers": ['shift', 'lshift', 'rshift', 'ctrl', 'lctrl', 'rctrl', 'alt', 'lalt', 'ralt', 'win', 'lwin', 'rwin'],
        "Navigation": ['up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pgup', 'pagedown', 'pgdn'],
        "Special": ['escape', 'esc', 'tab', 'capslock', 'caps', 'space', 'enter', 'return', 'backspace', 'delete', 'insert', 'apps'],
        "Numpad": [k for k in KEY_NAME_TO_VK.keys() if k.startswith('num')],
        "Media": ['playpause', 'nexttrack', 'prevtrack', 'mediastop', 'mute', 'volumeup', 'volumedown', 'calculator', 'mail'],
        "Browser": [k for k in KEY_NAME_TO_VK.keys() if k.startswith('browser')],
        "Mouse (source only)": ['mouse3', 'middleclick', 'mouse4', 'mouse5'],
    }
    
    for category, keys in categories.items():
        available = [k for k in keys if k in KEY_NAME_TO_VK]
        if available:
            print(f"{category}:")
            print(f"  {', '.join(sorted(available))}")
            print()


def configure_copilot_cli(remapper: KeyRemapper):
    """Text-mode Copilot key configuration."""
    copilot = remapper.copilot

    print("\n" + "=" * 50)
    print("Copilot Key")
    print("=" * 50)
    print("The Copilot key does not have its own scan code - the keyboard")
    print(f"firmware sends a chord. Current chord: {copilot.chord_text()}")
    print("(the default, SHIFT+WIN+F23, is what almost every OEM uses)")
    print()
    print("  1. Detect my Copilot key")
    print("  2. Disable it")
    print("  3. Send other key(s) instead")
    print("  4. Launch a program")
    print("  5. Open a URL")
    print("  6. Leave it alone (pass through)")
    print("  0. Back")

    choice = input("\nEnter choice: ").strip()

    if choice == '1':
        print("\nPress your Copilot key now (Escape cancels)...")
        result: List = []
        done = threading.Event()

        def on_chord(chord):
            result.append(chord)
            done.set()

        if not remapper.start_capture(on_chord):
            print("✗ Could not start key capture.")
        elif not done.wait(timeout=15.0):
            remapper.cancel_capture()
            print("✗ Timed out.")
        elif result and result[0]:
            modifiers, vk = result[0]
            copilot = CopilotConfig(
                enabled=copilot.enabled, modifiers=modifiers, key=vk,
                mode=copilot.mode, value=copilot.value
            )
            remapper.set_copilot(copilot)
            remapper.save_config()
            print(f"\n✓ Detected: {copilot.chord_text()}")
        else:
            print("Cancelled.")

    elif choice in ('2', '3', '4', '5', '6'):
        mode = {'2': 'disable', '3': 'keys', '4': 'launch',
                '5': 'url', '6': 'passthrough'}[choice]
        value = ""
        if mode == 'keys':
            value = input("Key(s) to send (e.g. ctrl+shift+p): ").strip()
        elif mode == 'launch':
            value = input("Program or file to launch: ").strip()
        elif mode == 'url':
            value = input("URL to open: ").strip()

        updated = CopilotConfig(
            enabled=(mode != 'passthrough'),
            modifiers=copilot.modifiers,
            key=copilot.key,
            mode=mode,
            value=value,
        )
        if remapper.set_copilot(updated):
            remapper.save_config()
            print(f"\n✓ Copilot key: {updated.action_text()}")
        else:
            print("\n✗ Invalid value.")

    if choice != '0':
        input("\nPress Enter to continue...")


def interactive_menu(remapper: KeyRemapper):
    """Interactive command-line menu"""
    
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_menu():
        clear_screen()
        print("=" * 50)
        print("       WINDOWS KEY REMAPPER v2.1")
        print("       Gaming Compatible Edition")
        print("=" * 50)

        if not remapper.running:
            status = "🔴 STOPPED"
        elif remapper.paused:
            status = "🟠 PAUSED"
        else:
            status = "🟢 ACTIVE"
        print(f"\nStatus: {status}")
        print(f"Active Mappings: {len(remapper.mappings)} | Blocked Keys: {len(remapper.blocked_keys)}")
        copilot = remapper.copilot
        print(f"Copilot Key: {copilot.chord_text()} -> "
              f"{copilot.action_text() if copilot.enabled else 'not managed'}")
        print()
        print("=== Key Mappings ===")
        print("  1. Add mapping")
        print("  2. Remove mapping")
        print("  3. List mappings")
        print("  4. Toggle mapping on/off")
        print()
        print("=== Block Keys (Gaming) ===")
        print("  5. Block a key (disable completely)")
        print("  6. Unblock a key")
        print("  7. List blocked keys")
        print("  8. Toggle blocked key on/off")
        print()
        print("=== Copilot Key ===")
        print("  9. Configure the Copilot key")
        print()
        print("=== Control ===")
        print("  S. Start remapper")
        print("  X. Stop remapper")
        print("  P. Pause/resume (keeps the hook installed)")
        print("  W. Save configuration")
        print("  L. Load configuration")
        print("  K. Show available keys")
        print("  0. Exit")
        print()
    
    while True:
        try:
            print_menu()
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                print("\nAdd New Mapping")
                print("-" * 30)
                print("Format: key or modifier+key (e.g., 'capslock', 'ctrl+a', 'shift+f1')")
                source = input("Source key(s): ").strip()
                if not source:
                    continue
                target = input("Target key(s): ").strip()
                if not target:
                    continue
                hold = input("When held instead (optional, single keys only): ").strip()
                app = input("Only in this app (optional, e.g. game.exe): ").strip()
                desc = input("Description (optional): ").strip()

                conflict = remapper.find_conflict(source, app)
                if conflict:
                    print(f"\n⚠️  {conflict}")
                    if input("Replace it? (y/N): ").strip().lower() != 'y':
                        input("\nCancelled. Press Enter to continue...")
                        continue

                if remapper.add_mapping(source, target, desc, hold=hold, app=app):
                    print("\n✓ Mapping added successfully!")
                    remapper.save_config()
                else:
                    print("\n✗ Failed to add mapping. Check the key names.")
                    print("  (hold actions only work on single keys)")
                input("\nPress Enter to continue...")
                
            elif choice == '2':
                mappings = remapper.list_mappings()
                if not mappings:
                    print("\nNo mappings configured.")
                else:
                    print("\nCurrent Mappings:")
                    for i, m in enumerate(mappings, 1):
                        status = "✓" if m['enabled'] else "✗"
                        scope = f" [{m['app']}]" if m['app'] else ""
                        print(f"  {i}. [{status}] {m['source']} -> {m['target']}{scope}")

                    source = input("\nEnter source key to remove (or 'cancel'): ").strip()
                    if source.lower() != 'cancel':
                        app = input("Which app (blank for the global rule): ").strip()
                        if remapper.remove_mapping(source, app):
                            print("✓ Mapping removed!")
                            remapper.save_config()
                        else:
                            print("✗ Mapping not found.")
                input("\nPress Enter to continue...")
                
            elif choice == '3':
                mappings = remapper.list_mappings()
                print("\n" + "=" * 40)
                print("Current Mappings:")
                print("=" * 40)
                if not mappings:
                    print("  No mappings configured.")
                else:
                    for m in mappings:
                        status = "ENABLED" if m['enabled'] else "DISABLED"
                        extras = []
                        if m['hold']:
                            extras.append(f"hold: {m['hold']}")
                        if m['app']:
                            extras.append(f"only in {m['app']}")
                        suffix = f" ({', '.join(extras)})" if extras else ""
                        print(f"  {m['source']} -> {m['target']}{suffix} [{status}]")
                        if m['description']:
                            print(f"    Description: {m['description']}")
                input("\nPress Enter to continue...")
                
            elif choice == '4':
                source = input("Enter source key to toggle: ").strip()
                app = input("Which app (blank for the global rule): ").strip()
                if remapper.toggle_mapping(source, app):
                    print("✓ Mapping toggled!")
                    remapper.save_config()
                else:
                    print("✗ Mapping not found.")
                input("\nPress Enter to continue...")
            
            # === Block Keys Section ===
            elif choice == '5':
                print("\nBlock a Key (Disable Completely)")
                print("-" * 30)
                print("This will completely disable a key - useful for gaming.")
                print("Format: key or modifier+key (e.g., '/', 'ctrl+/', 'f1')")
                key = input("Key to block: ").strip()
                if not key:
                    continue
                app = input("Only in this app (optional, e.g. game.exe): ").strip()
                desc = input("Description (optional): ").strip()

                if remapper.block_key(key, desc, app=app):
                    print(f"\n✓ Key '{key}' is now blocked!")
                    remapper.save_config()
                else:
                    print("\n✗ Failed to block key. Check the key name.")
                input("\nPress Enter to continue...")
                
            elif choice == '6':
                blocked = remapper.list_blocked_keys()
                if not blocked:
                    print("\nNo keys are currently blocked.")
                else:
                    print("\nCurrently Blocked Keys:")
                    for i, b in enumerate(blocked, 1):
                        status = "✓" if b['enabled'] else "✗"
                        scope = f" [{b['app']}]" if b['app'] else ""
                        print(f"  {i}. [{status}] {b['key']}{scope} - {b['description']}")

                    key = input("\nEnter key to unblock (or 'cancel'): ").strip()
                    if key.lower() != 'cancel':
                        app = input("Which app (blank for the global rule): ").strip()
                        if remapper.unblock_key(key, app):
                            print(f"✓ Key '{key}' unblocked!")
                            remapper.save_config()
                        else:
                            print("✗ Key not found in blocked list.")
                input("\nPress Enter to continue...")
                
            elif choice == '7':
                blocked = remapper.list_blocked_keys()
                print("\n" + "=" * 40)
                print("Blocked Keys:")
                print("=" * 40)
                if not blocked:
                    print("  No keys are currently blocked.")
                else:
                    for b in blocked:
                        status = "ENABLED" if b['enabled'] else "DISABLED"
                        print(f"  {b['key']} [{status}]")
                        if b['description']:
                            print(f"    Description: {b['description']}")
                input("\nPress Enter to continue...")
                
            elif choice == '8':
                key = input("Enter blocked key to toggle: ").strip()
                app = input("Which app (blank for the global rule): ").strip()
                if remapper.toggle_blocked_key(key, app):
                    print("✓ Blocked key toggled!")
                    remapper.save_config()
                else:
                    print("✗ Key not found in blocked list.")
                input("\nPress Enter to continue...")
            
            # === Copilot Section ===
            elif choice == '9':
                configure_copilot_cli(remapper)

            # === Control Section ===
            elif choice.lower() == 's':
                if remapper.running:
                    print("Remapper is already running.")
                elif not remapper.mappings and not remapper.blocked_keys:
                    print("No mappings or blocked keys configured. Add some first.")
                else:
                    if remapper.start():
                        print("\n✓ Remapper started!")
                        print("Your key mappings and blocks are now active.")
                    else:
                        print("\n✗ Failed to start remapper.")
                input("\nPress Enter to continue...")
                
            elif choice.lower() == 'x':
                remapper.stop()
                print("\n✓ Remapper stopped.")
                input("\nPress Enter to continue...")

            elif choice.lower() == 'p':
                if not remapper.running:
                    print("\nRemapper is not running.")
                else:
                    remapper.set_paused(not remapper.paused)
                    print(f"\n✓ Remapper {'paused' if remapper.paused else 'resumed'}.")
                input("\nPress Enter to continue...")
                
            elif choice.lower() == 'w':
                if remapper.save_config():
                    print(f"\n✓ Configuration saved to {CONFIG_FILE}")
                else:
                    print("\n✗ Failed to save configuration.")
                input("\nPress Enter to continue...")
                
            elif choice.lower() == 'l':
                if remapper.load_config():
                    print(f"\n✓ Configuration loaded from {CONFIG_FILE}")
                else:
                    print("\n✗ Failed to load configuration (file may not exist).")
                input("\nPress Enter to continue...")
                
            elif choice.lower() == 'k':
                print_available_keys()
                input("\nPress Enter to continue...")
                
            elif choice == '0':
                remapper.stop()
                print("\nGoodbye!")
                break
                
            else:
                print("Invalid choice.")
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Stopping remapper...")
            remapper.stop()
            break
        except Exception:
            input("\nPress Enter to continue...")


def main():
    """Main entry point"""
    print("Initializing Key Remapper...")

    # Create remapper instance
    remapper = KeyRemapper()
    
    # Try to load existing config
    remapper.load_config()
    
    # Run interactive menu
    interactive_menu(remapper)


if __name__ == "__main__":
    main()
