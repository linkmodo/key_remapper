"""
Windows 11 Key Remapper with Gaming Support
============================================
A robust key remapping tool that works with games and applications.
Uses low-level Windows hooks for maximum compatibility.

Requirements:
- Windows 11 (also works on Windows 10)
- Python 3.8+
- Run as Administrator for full functionality

Author: Key Remapper
License: MIT
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import sys
import threading
import time
import atexit
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Set, Tuple
from pathlib import Path
from enum import IntEnum

# Windows API Constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_INJECTED = 0x00000010
LLKHF_LOWER_IL_INJECTED = 0x00000002

# Key event types
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001

# Input type
INPUT_KEYBOARD = 1

# Configuration file
CONFIG_FILE = Path(__file__).parent / "key_remap_config.json"


class VirtualKey(IntEnum):
    """Virtual Key Codes for Windows"""
    VK_LBUTTON = 0x01
    VK_RBUTTON = 0x02
    VK_CANCEL = 0x03
    VK_MBUTTON = 0x04
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
}

# Reverse mapping
VK_TO_KEY_NAME: Dict[int, str] = {v: k for k, v in KEY_NAME_TO_VK.items()}

# Extended keys that require the extended flag
EXTENDED_KEYS = {
    VirtualKey.VK_INSERT, VirtualKey.VK_DELETE, VirtualKey.VK_HOME,
    VirtualKey.VK_END, VirtualKey.VK_PRIOR, VirtualKey.VK_NEXT,
    VirtualKey.VK_LEFT, VirtualKey.VK_RIGHT, VirtualKey.VK_UP, VirtualKey.VK_DOWN,
    VirtualKey.VK_SNAPSHOT, VirtualKey.VK_DIVIDE, VirtualKey.VK_NUMLOCK,
    VirtualKey.VK_RCONTROL, VirtualKey.VK_RMENU,
}


# Windows structures
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
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
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
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

# Hook callback type
HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT))


@dataclass
class KeyMapping:
    """Represents a key mapping configuration"""
    source_keys: Tuple[int, ...]  # Source key(s) - tuple of VK codes
    target_keys: Tuple[int, ...]  # Target key(s) - tuple of VK codes
    enabled: bool = True
    description: str = ""


@dataclass
class BlockedKey:
    """Represents a blocked/disabled key"""
    key: Tuple[int, ...]  # Key(s) to block - tuple of VK codes
    enabled: bool = True
    description: str = ""


@dataclass
class RemapperState:
    """Tracks the current state of the remapper"""
    active_modifiers: Set[int] = field(default_factory=set)
    pressed_keys: Set[int] = field(default_factory=set)
    suppressed_keys: Set[int] = field(default_factory=set)


class KeyRemapper:
    """
    Low-level Windows key remapper with gaming support.
    Uses Windows hooks for maximum compatibility with games and applications.
    """
    
    def __init__(self):
        self.mappings: Dict[Tuple[int, ...], KeyMapping] = {}
        self.blocked_keys: Dict[Tuple[int, ...], BlockedKey] = {}  # Keys to completely disable
        self.state = RemapperState()
        self.hook_handle = None
        self.hook_callback = None
        self.running = False
        self.message_thread = None
        self._lock = threading.Lock()
        
        # Marker to identify our own injected events
        self._injection_marker = ctypes.pointer(ctypes.c_ulong(0xDEADBEEF))
        
        # Register cleanup on exit
        atexit.register(self.stop)
    
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
        modifier_vks = {
            VirtualKey.VK_CONTROL, VirtualKey.VK_LCONTROL, VirtualKey.VK_RCONTROL,
            VirtualKey.VK_SHIFT, VirtualKey.VK_LSHIFT, VirtualKey.VK_RSHIFT,
            VirtualKey.VK_MENU, VirtualKey.VK_LMENU, VirtualKey.VK_RMENU,
            VirtualKey.VK_LWIN, VirtualKey.VK_RWIN
        }
        
        modifiers = sorted([k for k in keys if k in modifier_vks])
        non_modifiers = [k for k in keys if k not in modifier_vks]
        
        return tuple(modifiers + non_modifiers)
    
    def vk_to_string(self, vk_codes: Tuple[int, ...]) -> str:
        """Convert VK codes back to a readable string"""
        names = []
        for vk in vk_codes:
            name = VK_TO_KEY_NAME.get(vk, f"0x{vk:02X}")
            names.append(name.upper())
        return '+'.join(names)
    
    def add_mapping(self, source: str, target: str, description: str = "") -> bool:
        """
        Add a key mapping.
        
        Args:
            source: Source key(s) string (e.g., 'capslock', 'ctrl+a')
            target: Target key(s) string (e.g., 'escape', 'ctrl+c')
            description: Optional description
            
        Returns:
            True if mapping was added successfully
        """
        try:
            source_keys = self.parse_key_string(source)
            target_keys = self.parse_key_string(target)
            
            mapping = KeyMapping(
                source_keys=source_keys,
                target_keys=target_keys,
                enabled=True,
                description=description or f"{source} -> {target}"
            )
            
            with self._lock:
                self.mappings[source_keys] = mapping
            
            return True
            
        except ValueError:
            return False
    
    def remove_mapping(self, source: str) -> bool:
        """Remove a key mapping by source key string"""
        try:
            source_keys = self.parse_key_string(source)
            
            with self._lock:
                if source_keys in self.mappings:
                    del self.mappings[source_keys]
                    return True
                else:
                    return False
                    
        except ValueError:
            return False
    
    def toggle_mapping(self, source: str) -> bool:
        """Toggle a mapping on/off"""
        try:
            source_keys = self.parse_key_string(source)
            
            with self._lock:
                if source_keys in self.mappings:
                    self.mappings[source_keys].enabled = not self.mappings[source_keys].enabled
                    return True
                return False
                
        except ValueError:
            return False
    
    def block_key(self, key: str, description: str = "") -> bool:
        """
        Block/disable a key completely (key press will be ignored).
        
        Args:
            key: Key(s) string to block (e.g., '/', 'ctrl+/', 'f1')
            description: Optional description
            
        Returns:
            True if key was blocked successfully
        """
        try:
            key_codes = self.parse_key_string(key)
            
            blocked = BlockedKey(
                key=key_codes,
                enabled=True,
                description=description or f"Block {key}"
            )
            
            with self._lock:
                self.blocked_keys[key_codes] = blocked
            
            return True
            
        except ValueError:
            return False
    
    def unblock_key(self, key: str) -> bool:
        """Unblock a previously blocked key"""
        try:
            key_codes = self.parse_key_string(key)
            
            with self._lock:
                if key_codes in self.blocked_keys:
                    del self.blocked_keys[key_codes]
                    return True
                else:
                    return False
                    
        except ValueError:
            return False
    
    def toggle_blocked_key(self, key: str) -> bool:
        """Toggle a blocked key on/off"""
        try:
            key_codes = self.parse_key_string(key)
            
            with self._lock:
                if key_codes in self.blocked_keys:
                    self.blocked_keys[key_codes].enabled = not self.blocked_keys[key_codes].enabled
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
                    "description": blocked.description
                })
        return result
    
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
    
    def _is_injected(self, kb_struct: KBDLLHOOKSTRUCT) -> bool:
        """Check if the event was injected by us"""
        if kb_struct.flags & LLKHF_INJECTED:
            try:
                if kb_struct.dwExtraInfo and kb_struct.dwExtraInfo.contents.value == 0xDEADBEEF:
                    return True
            except (ValueError, OSError):
                pass
        return False
    
    def _keyboard_callback(self, nCode: int, wParam: wintypes.WPARAM, 
                           lParam: ctypes.POINTER(KBDLLHOOKSTRUCT)) -> int:
        """Low-level keyboard hook callback"""
        if nCode < 0:
            return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)
        
        try:
            kb = lParam.contents
            vk_code = kb.vkCode
            is_keydown = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_keyup = wParam in (WM_KEYUP, WM_SYSKEYUP)
            
            # Skip our own injected events
            if self._is_injected(kb):
                return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)
            
            # Track modifier state
            modifier_vks = {
                VirtualKey.VK_CONTROL, VirtualKey.VK_LCONTROL, VirtualKey.VK_RCONTROL,
                VirtualKey.VK_SHIFT, VirtualKey.VK_LSHIFT, VirtualKey.VK_RSHIFT,
                VirtualKey.VK_MENU, VirtualKey.VK_LMENU, VirtualKey.VK_RMENU,
            }
            
            if vk_code in modifier_vks:
                if is_keydown:
                    self.state.active_modifiers.add(vk_code)
                elif is_keyup:
                    self.state.active_modifiers.discard(vk_code)
            
            # Build current key combination
            current_combo = tuple(sorted(self.state.active_modifiers)) + (vk_code,)
            single_key = (vk_code,)
            
            # Check for blocked keys first (try combo first, then single key)
            is_blocked = False
            with self._lock:
                if current_combo in self.blocked_keys and self.blocked_keys[current_combo].enabled:
                    is_blocked = True
                elif single_key in self.blocked_keys and self.blocked_keys[single_key].enabled:
                    is_blocked = True
            
            if is_blocked:
                # Block the key completely - don't send anything
                if is_keydown:
                    self.state.suppressed_keys.add(vk_code)
                    return 1  # Block the key
                elif is_keyup and vk_code in self.state.suppressed_keys:
                    self.state.suppressed_keys.discard(vk_code)
                    return 1  # Block the key release too
            
            # Check for mappings (try combo first, then single key)
            mapping = None
            matched_source = None
            
            with self._lock:
                if current_combo in self.mappings and self.mappings[current_combo].enabled:
                    mapping = self.mappings[current_combo]
                    matched_source = current_combo
                elif single_key in self.mappings and self.mappings[single_key].enabled:
                    mapping = self.mappings[single_key]
                    matched_source = single_key
            
            if mapping:
                if is_keydown:
                    # Suppress the original key
                    self.state.suppressed_keys.add(vk_code)
                    # Send the target key(s)
                    self._send_key_combination(mapping.target_keys, key_up=False)
                    return 1  # Block original key
                    
                elif is_keyup and vk_code in self.state.suppressed_keys:
                    self.state.suppressed_keys.discard(vk_code)
                    # Release the target key(s)
                    self._send_key_combination(mapping.target_keys, key_up=True)
                    return 1  # Block original key
            
        except Exception:
            pass
        
        return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)
    
    def _message_loop(self):
        """Windows message loop for the hook"""
        # Store this thread's ID so we can post quit message to it
        self._message_thread_id = kernel32.GetCurrentThreadId()
        
        msg = wintypes.MSG()
        while self.running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    
    def start(self) -> bool:
        """Start the key remapper"""
        if self.running:
            return False
        
        if not self.mappings and not self.blocked_keys:
            return False
        
        try:
            # Create the hook callback (must keep reference!)
            self.hook_callback = HOOKPROC(self._keyboard_callback)
            
            # Install the hook
            self.hook_handle = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self.hook_callback,
                None,
                0
            )
            
            if not self.hook_handle:
                return False
            
            self.running = True
            
            # Start message loop in a separate thread
            self.message_thread = threading.Thread(target=self._message_loop, daemon=True)
            self.message_thread.start()
            
            return True
            
        except Exception:
            return False
    
    def stop(self):
        """Stop the key remapper"""
        if not self.running:
            return
        
        self.running = False
        
        # Post quit message to exit message loop (to the correct thread)
        if hasattr(self, '_message_thread_id') and self._message_thread_id:
            user32.PostThreadMessageW(
                self._message_thread_id,
                0x0012,  # WM_QUIT
                0, 0
            )
            self._message_thread_id = None
        
        # Unhook after posting quit message
        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None
        
        self.state = RemapperState()
    
    def save_config(self, filepath: Path = CONFIG_FILE) -> bool:
        """Save current mappings and blocked keys to a JSON file"""
        try:
            config = {
                "mappings": [
                    {
                        "source": self.vk_to_string(m.source_keys),
                        "target": self.vk_to_string(m.target_keys),
                        "enabled": m.enabled,
                        "description": m.description
                    }
                    for m in self.mappings.values()
                ],
                "blocked_keys": [
                    {
                        "key": self.vk_to_string(b.key),
                        "enabled": b.enabled,
                        "description": b.description
                    }
                    for b in self.blocked_keys.values()
                ]
            }
            
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=4)
            
            return True
            
        except Exception:
            return False
    
    def load_config(self, filepath: Path = CONFIG_FILE) -> bool:
        """Load mappings and blocked keys from a JSON file"""
        try:
            if not filepath.exists():
                return False
            
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            with self._lock:
                self.mappings.clear()
                self.blocked_keys.clear()
            
            # Load mappings
            for mapping_data in config.get("mappings", []):
                source = mapping_data.get("source", "")
                target = mapping_data.get("target", "")
                description = mapping_data.get("description", "")
                
                if source and target:
                    self.add_mapping(source, target, description)
                    
                    # Handle enabled state
                    if not mapping_data.get("enabled", True):
                        self.toggle_mapping(source)
            
            # Load blocked keys
            for blocked_data in config.get("blocked_keys", []):
                key = blocked_data.get("key", "")
                description = blocked_data.get("description", "")
                
                if key:
                    self.block_key(key, description)
                    
                    # Handle enabled state
                    if not blocked_data.get("enabled", True):
                        self.toggle_blocked_key(key)
            
            return True
            
        except (json.JSONDecodeError, Exception):
            return False
    
    def list_mappings(self) -> List[Dict]:
        """Get a list of all current mappings"""
        result = []
        with self._lock:
            for mapping in self.mappings.values():
                result.append({
                    "source": self.vk_to_string(mapping.source_keys),
                    "target": self.vk_to_string(mapping.target_keys),
                    "enabled": mapping.enabled,
                    "description": mapping.description
                })
        return result


def check_admin() -> bool:
    """Check if running with administrator privileges"""
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
        "Special": ['escape', 'esc', 'tab', 'capslock', 'caps', 'space', 'enter', 'return', 'backspace', 'delete', 'insert'],
        "Numpad": [k for k in KEY_NAME_TO_VK.keys() if k.startswith('num')],
    }
    
    for category, keys in categories.items():
        available = [k for k in keys if k in KEY_NAME_TO_VK]
        if available:
            print(f"{category}:")
            print(f"  {', '.join(sorted(available))}")
            print()


def interactive_menu(remapper: KeyRemapper):
    """Interactive command-line menu"""
    
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_menu():
        clear_screen()
        print("=" * 50)
        print("       WINDOWS KEY REMAPPER v1.0")
        print("       Gaming Compatible Edition")
        print("=" * 50)
        
        if not check_admin():
            print("\n⚠️  WARNING: Not running as Administrator!")
            print("   Some features may not work in games.\n")
        
        status = "🟢 ACTIVE" if remapper.running else "🔴 STOPPED"
        print(f"\nStatus: {status}")
        print(f"Active Mappings: {len(remapper.mappings)} | Blocked Keys: {len(remapper.blocked_keys)}")
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
        print("=== Control ===")
        print("  S. Start remapper")
        print("  X. Stop remapper")
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
                desc = input("Description (optional): ").strip()
                
                if remapper.add_mapping(source, target, desc):
                    print("\n✓ Mapping added successfully!")
                else:
                    print("\n✗ Failed to add mapping. Check the key names.")
                input("\nPress Enter to continue...")
                
            elif choice == '2':
                mappings = remapper.list_mappings()
                if not mappings:
                    print("\nNo mappings configured.")
                else:
                    print("\nCurrent Mappings:")
                    for i, m in enumerate(mappings, 1):
                        status = "✓" if m['enabled'] else "✗"
                        print(f"  {i}. [{status}] {m['source']} -> {m['target']}")
                    
                    source = input("\nEnter source key to remove (or 'cancel'): ").strip()
                    if source.lower() != 'cancel':
                        if remapper.remove_mapping(source):
                            print("✓ Mapping removed!")
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
                        print(f"  {m['source']} -> {m['target']} [{status}]")
                        if m['description']:
                            print(f"    Description: {m['description']}")
                input("\nPress Enter to continue...")
                
            elif choice == '4':
                source = input("Enter source key to toggle: ").strip()
                if remapper.toggle_mapping(source):
                    print("✓ Mapping toggled!")
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
                desc = input("Description (optional): ").strip()
                
                if remapper.block_key(key, desc):
                    print(f"\n✓ Key '{key}' is now blocked!")
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
                        print(f"  {i}. [{status}] {b['key']} - {b['description']}")
                    
                    key = input("\nEnter key to unblock (or 'cancel'): ").strip()
                    if key.lower() != 'cancel':
                        if remapper.unblock_key(key):
                            print(f"✓ Key '{key}' unblocked!")
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
                if remapper.toggle_blocked_key(key):
                    print("✓ Blocked key toggled!")
                else:
                    print("✗ Key not found in blocked list.")
                input("\nPress Enter to continue...")
            
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
    
    # Check for admin rights
    if not check_admin():
        print("\n" + "=" * 50)
        print("WARNING: Not running as Administrator!")
        print("=" * 50)
        print("For full compatibility with games, please run")
        print("this program as Administrator.")
        print("Right-click -> Run as administrator")
        print("=" * 50 + "\n")
    
    # Create remapper instance
    remapper = KeyRemapper()
    
    # Try to load existing config
    remapper.load_config()
    
    # Run interactive menu
    interactive_menu(remapper)


if __name__ == "__main__":
    main()
