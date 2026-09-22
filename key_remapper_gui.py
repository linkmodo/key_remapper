"""
Windows Key Remapper - Modern GUI Edition
==========================================
A modern GUI wrapper for the key remapper using customtkinter.
Supports system tray operation for gaming.

Requirements:
- Windows 11 (also works on Windows 10)
- Python 3.8+
- Administrator rights are optional (only needed for elevated windows)
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
import time
import json
import queue
import webbrowser
from pathlib import Path
from typing import Callable, Optional
import sys
import os

# Import the core remapper functionality
from key_remapper import (
    KeyRemapper, CONFIG_FILE, CONFIG_DIR, KEY_NAME_TO_VK, VK_TO_KEY_NAME,
    CopilotConfig, DEFAULT_COPILOT_KEY, Settings,
    COMMON_APPS, COMMON_TARGETS, vk_name, SingleInstance, key_reference,
    is_run_at_startup, set_run_at_startup, check_admin, logger,
    __version__, PROJECT_URL, DONATE_URL
)

# Try to import pystray for system tray support
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Secondary (gray) buttons. The hover used to be a lighter gray, which barely
# registered - a clear accent makes it obvious what the pointer is on.
GRAY_BUTTON = "#7f8c8d"
GRAY_BUTTON_HOVER = "#2e86c1"

# Start / Stop. Only one of the pair is clickable at a time; the other shows
# the current state, so it gets a darker fill with *legible* text rather than
# CustomTkinter's default disabled gray, which vanishes on green or red.
START_COLOR, START_HOVER, START_IDLE = "#27ae60", "#2ecc71", "#1e7a45"
STOP_COLOR, STOP_HOVER, STOP_IDLE = "#c0392b", "#e74c3c", "#7d2a22"
IDLE_TEXT = "#e8f6ef"


def _window_scaling(widget) -> float:
    """
    How many real pixels customtkinter draws per geometry() pixel.

    Sizes passed to geometry() are scaled by this, while winfo_screenheight()
    reports real pixels - mixing the two silently oversizes windows on a
    high-DPI display.
    """
    try:
        return ctk.ScalingTracker.get_window_scaling(widget) or 1.0
    except Exception:
        return 1.0


def _backup_folder() -> Path:
    """Where Save/Load dialogs start: Documents, never the live settings folder."""
    documents = Path.home() / "Documents"
    return documents if documents.is_dir() else Path.home()


def _same_file(a, b) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """
    A scrollable frame whose scrollbar only appears when it is needed.

    CustomTkinter always reserves and draws the scrollbar; here it is hidden
    while the content fits, and restored the moment it does not.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scrollbar_visible = True
        self.bind("<Configure>", self._refresh_scrollbar, add="+")
        self._parent_canvas.bind("<Configure>", self._refresh_scrollbar, add="+")
        # A tab that has never been shown reports no height, so re-check when it
        # is first mapped - that is the moment the bar would become visible
        self._parent_canvas.bind("<Map>", self._refresh_scrollbar, add="+")
        self.after(120, self._refresh_scrollbar)

    def _content_overflows(self) -> bool:
        visible = self._parent_canvas.winfo_height()
        if visible <= 1:
            # Not laid out yet (e.g. a background tab): nothing to scroll past
            return False
        bbox = self._parent_canvas.bbox("all")
        if not bbox:
            return False
        return (bbox[3] - bbox[1]) > visible + 1

    def _refresh_scrollbar(self, event=None):
        try:
            needed = self._content_overflows()
            if needed == self._scrollbar_visible:
                return
            self._scrollbar_visible = needed
            if needed:
                self._scrollbar.grid()
            else:
                self._scrollbar.grid_remove()
        except Exception:
            logger.debug("Could not update scrollbar visibility", exc_info=True)


class UiQueueMixin:
    """
    Marshals work from background threads onto the Tk thread.

    ``widget.after()`` registers a Tcl command and must therefore be called from
    the thread that owns the interpreter - calling it from the hook thread
    raises "main thread is not in main loop" and the callback is lost. Anything
    arriving from another thread goes through this queue instead.
    """

    def _init_ui_queue(self, interval_ms: int = 40):
        self._ui_queue = queue.Queue()
        self._ui_pump_interval = interval_ms
        self._ui_pump_id = None
        self._pump_ui_queue()

    def post_to_ui(self, func: Callable):
        """Safe to call from any thread."""
        self._ui_queue.put(func)

    def _pump_ui_queue(self):
        try:
            while True:
                try:
                    func = self._ui_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    func()
                except Exception:
                    logger.exception("UI callback failed")
        finally:
            if self.winfo_exists():
                self._ui_pump_id = self.after(self._ui_pump_interval, self._pump_ui_queue)

    def destroy(self):
        # Cancel the pending tick, otherwise Tcl complains about an invalid
        # command name once the widget is gone
        if getattr(self, '_ui_pump_id', None):
            try:
                self.after_cancel(self._ui_pump_id)
            except Exception:
                pass
            self._ui_pump_id = None
        super().destroy()


class KeyCaptureDialog(UiQueueMixin, ctk.CTkToplevel):
    """
    Dialog to capture a key press.

    Prefers the remapper's low-level hook, which sees combinations tkinter
    cannot - anything involving the Windows key, F13-F24 or the Copilot chord.
    Falls back to tkinter key bindings when no remapper is available.
    """

    def __init__(self, parent, title: str = "Press a Key", remapper: KeyRemapper = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("470x390")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.detected_keys = []
        self.remapper = remapper or getattr(parent, 'remapper', None)
        self.capturing = False

        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 470) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 390) // 2
        self.geometry(f"+{x}+{y}")

        # UI
        self.label = ctk.CTkLabel(
            self,
            text="Press any key or key combination...",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.label.pack(pady=(18, 8))

        self.detected_label = ctk.CTkLabel(
            self,
            text="Detected: (none)",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.detected_label.pack(pady=(5, 0))

        # What the keyboard actually reported - the only way to tell two keys
        # that share a virtual key code apart
        self.hardware_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=10), text_color="gray"
        )
        self.hardware_label.pack(pady=(0, 4))

        if self.remapper:
            self.info_label = ctk.CTkLabel(
                self,
                text="Click below, then press the keys. Everything is intercepted\n"
                     "until you do, so Win and Copilot combinations work too.",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            self.info_label.pack(pady=4)

            self.capture_btn = ctk.CTkButton(
                self, text="🎯 Start capturing", command=self._start_low_level_capture, width=170
            )
            self.capture_btn.pack(pady=4)

            # The Fn key cannot be captured on most keyboards - say so here,
            # where someone is about to try it, rather than letting them guess
            ctk.CTkLabel(
                self,
                text="Using Fn? Press the whole combination (e.g. Fn+F12).\n"
                     "Fn itself is invisible to Windows on most keyboards, so what\n"
                     "gets recorded is the key your keyboard actually sends.",
                font=ctk.CTkFont(size=10), text_color="#f39c12",
                justify="center", wraplength=430
            ).pack(pady=(10, 4))
        else:
            self.info_label = ctk.CTkLabel(
                self,
                text="Hold modifiers (Ctrl/Shift/Alt) then press a key\n"
                     "Note: Win key combos may not detect - type manually below",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            self.info_label.pack(pady=5)

        # Manual entry option
        self.manual_entry = ctk.CTkEntry(self, width=300, placeholder_text="Or type manually: e.g., win+shift+f23")
        self.manual_entry.pack(pady=5)
        self.manual_entry.bind("<Return>", self._on_manual_entry)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=12)

        self.use_btn = ctk.CTkButton(btn_frame, text="Use This Key", command=self._use_key, width=120, state="disabled")
        self.use_btn.pack(side="left", padx=5)

        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, width=100)
        self.cancel_btn.pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Bind key events (fallback path, and harmless alongside the hook)
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self.focus_force()
        self._init_ui_queue()

    # --- low-level capture --------------------------------------------

    def _start_low_level_capture(self):
        """Swallow all input until one chord is pressed"""
        if self.capturing or not self.remapper:
            return

        def on_chord(chord):
            # Called on the hook thread - hand back to the UI thread
            self.post_to_ui(lambda: self._finish_capture(chord))

        if not self.remapper.start_capture(on_chord):
            self.detected_label.configure(text="Could not start capture", text_color="#e74c3c")
            return

        self.capturing = True
        self.capture_btn.configure(text="Press keys now… (Esc cancels)", state="disabled")
        self.label.configure(text="Listening…")

    def _finish_capture(self, chord):
        self.capturing = False
        if not self.winfo_exists():
            return
        self.capture_btn.configure(text="🎯 Start capturing", state="normal")
        self._finish_low_level_capture(chord)

    def _finish_low_level_capture(self, chord):
        self.label.configure(text="Press any key or key combination...")

        if not chord:
            self.detected_label.configure(text="Cancelled", text_color="gray")
            return

        self.detected_keys = list(chord.modifiers) + [vk_name(chord.vk)]
        self.hardware_label.configure(text=f"Keyboard reported {chord.hardware_text()}")
        self._refresh_detected()

    def _refresh_detected(self):
        """Redraw the detected combination."""
        if not self.detected_keys:
            return
        self.detected_label.configure(
            text=f"Detected: {'+'.join(self.detected_keys)}", text_color="#27ae60"
        )
        self.use_btn.configure(state="normal")

    def _on_cancel(self):
        if self.capturing and self.remapper:
            self.remapper.cancel_capture()
        self.destroy()

    def _on_key_press(self, event):
        """Handle key press event"""
        # Get the main key first
        key_name = self._get_key_name(event)

        # Skip if no valid key detected
        if not key_name:
            return

        # Build key combination
        keys = []

        # Check if this is a modifier key being pressed by itself
        modifier_keys = ["ctrl", "lctrl", "rctrl", "shift", "lshift", "rshift",
                        "alt", "lalt", "ralt", "win", "lwin", "rwin"]

        if key_name in modifier_keys:
            # Just show the modifier key itself
            keys.append(key_name)
        else:
            # Check modifiers from event state (only for non-modifier keys)
            if event.state & 0x0004:  # Control
                keys.append("ctrl")
            if event.state & 0x0001:  # Shift
                keys.append("shift")
            if event.state & 0x20000 or event.state & 0x0008:  # Alt
                keys.append("alt")
            # Note: Win key state is unreliable in tkinter, so we detect it from keysym

            # Add the main key
            keys.append(key_name)

        if keys:
            self.detected_keys = keys
            self.hardware_label.configure(text="")
            self._refresh_detected()

    def _on_key_release(self, event):
        """Handle key release - finalize detection"""
        pass

    def _get_key_name(self, event):
        """Convert tkinter key event to our key name format"""
        key = event.keysym.lower()

        # Map tkinter key names to our format
        key_map = {
            "control_l": "lctrl", "control_r": "rctrl", "control": "ctrl",
            "shift_l": "lshift", "shift_r": "rshift", "shift": "shift",
            "alt_l": "lalt", "alt_r": "ralt", "alt": "alt",
            "win_l": "lwin", "win_r": "rwin", "super_l": "lwin", "super_r": "rwin",
            "caps_lock": "capslock", "num_lock": "numlock", "scroll_lock": "scrolllock",
            "prior": "pageup", "next": "pagedown",
            "kp_0": "num0", "kp_1": "num1", "kp_2": "num2", "kp_3": "num3",
            "kp_4": "num4", "kp_5": "num5", "kp_6": "num6", "kp_7": "num7",
            "kp_8": "num8", "kp_9": "num9",
            "kp_add": "numplus", "kp_subtract": "numminus",
            "kp_multiply": "nummultiply", "kp_divide": "numdivide",
            "kp_decimal": "numdecimal",
            "bracketleft": "lbracket", "bracketright": "rbracket",
            "backslash": "backslash", "apostrophe": "quote",
            "grave": "grave", "minus": "minus", "equal": "equals",
        }

        return key_map.get(key, key if len(key) == 1 or key.startswith('f') and key[1:].isdigit() else key)

    def _on_manual_entry(self, event):
        """Handle manual entry of key combination"""
        text = self.manual_entry.get().strip()
        if text:
            self.result = text
            self.destroy()

    def _use_key(self):
        """Use the detected key combination"""
        if self.detected_keys:
            self.result = "+".join(self.detected_keys)
            self.destroy()


class KeyReferenceWindow(ctk.CTkToplevel):
    """
    Every key name, grouped, searchable and clickable.

    Browse mode (no ``entry``): clicking a key copies its name.
    Pick mode: clicking keys builds a combination straight into ``entry`` -
    ctrl, then s, gives "ctrl+s" - with Remove last / Clear / Done.
    """

    # Short names (a, 7, f12) get compact chips so letters and digits don't
    # push the more interesting groups off the first screen
    COLUMNS, CHIP_WIDTH = 5, 112
    COMPACT_COLUMNS, COMPACT_WIDTH = 10, 52

    def __init__(self, parent, entry=None, field_name: str = "", allow_source_only: bool = True):
        super().__init__(parent)
        self.parent = parent
        self.entry = entry
        self.picking = entry is not None
        self.allow_source_only = allow_source_only
        self._filter_id = None

        self.title(f"Choose keys — {field_name}" if self.picking else "Available Keys")
        height = min(680, max(420, int(parent.winfo_screenheight() / _window_scaling(parent)) - 110))
        self.geometry(f"680x{height}")
        self.minsize(560, 380)
        self.transient(parent)

        self.update_idletasks()
        x = parent.winfo_rootx() + 40
        y = max(0, parent.winfo_rooty() - 20)
        self.geometry(f"+{x}+{y}")

        # --- header --------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))

        if self.picking:
            ctk.CTkLabel(
                header, text=f"Click keys to build the {field_name.lower()}",
                font=ctk.CTkFont(size=15, weight="bold")
            ).pack(anchor="w")

            build = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=6)
            build.pack(fill="x", padx=14, pady=(4, 6))
            ctk.CTkLabel(build, text="Current:", text_color="gray").pack(side="left", padx=(12, 6), pady=8)
            self.current_label = ctk.CTkLabel(
                build, text="", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                text_color="#5dade2"
            )
            self.current_label.pack(side="left", pady=8)
            ctk.CTkButton(
                build, text="Done", width=70, command=self._close,
                fg_color=START_COLOR, hover_color=START_HOVER
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                build, text="Clear", width=64, command=self._clear,
                fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER
            ).pack(side="right", padx=4, pady=8)
            ctk.CTkButton(
                build, text="⌫ Remove last", width=110, command=self._remove_last,
                fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER
            ).pack(side="right", padx=4, pady=8)
            self._refresh_current()
        else:
            ctk.CTkLabel(
                header, text="Available keys", font=ctk.CTkFont(size=15, weight="bold")
            ).pack(anchor="w")
            ctk.CTkLabel(
                header, text="Type these names in any key field. Click a key to copy its name.",
                font=ctk.CTkFont(size=11), text_color="gray"
            ).pack(anchor="w")

        self.search_entry = ctk.CTkEntry(
            self, placeholder_text="Search — e.g. volume, arrow, f1, bracket"
        )
        self.search_entry.pack(fill="x", padx=14, pady=(4, 6))
        self.search_entry.bind("<KeyRelease>", self._schedule_filter)

        # --- what the pointer is over ------------------------------------
        # Packed before the body so it keeps its place at the bottom
        self.info_label = ctk.CTkLabel(
            self, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=12), text_color="#aeb6bf"
        )
        self.info_label.pack(side="bottom", fill="x", padx=16, pady=(4, 10))
        self._show_default_info()

        # --- the keys -------------------------------------------------------
        self.body = AutoHideScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=8)

        self.groups = []   # (frame, [(chip, key, haystack)])
        for group in key_reference():
            frame = ctk.CTkFrame(self.body, fg_color="transparent")
            frame.pack(fill="x", pady=(6, 2))

            ctk.CTkLabel(
                frame, text=group["title"], font=ctk.CTkFont(size=13, weight="bold")
            ).pack(anchor="w", padx=6)
            if group["note"]:
                ctk.CTkLabel(
                    frame, text=group["note"], font=ctk.CTkFont(size=11), text_color="gray",
                    wraplength=600, justify="left"
                ).pack(anchor="w", padx=6)

            grid = ctk.CTkFrame(frame, fg_color="transparent")
            grid.pack(anchor="w", padx=2, pady=(4, 2))

            compact = all(len(key["name"]) <= 3 for key in group["keys"])
            width = self.COMPACT_WIDTH if compact else self.CHIP_WIDTH
            columns = self.COMPACT_COLUMNS if compact else self.COLUMNS

            chips = []
            for key in group["keys"]:
                usable = key["target"] or self.allow_source_only or not self.picking
                chip = ctk.CTkButton(
                    grid, text=key["name"], width=width, height=28,
                    font=ctk.CTkFont(family="Consolas", size=12),
                    fg_color="#34495e" if usable else "#2c2f33",
                    hover_color=GRAY_BUTTON_HOVER,
                    text_color_disabled="#6b7178",
                    state="normal" if usable else "disabled",
                    command=lambda k=key: self._on_key(k),
                )
                chip.bind("<Enter>", lambda e, k=key, u=usable: self._show_info(k, u), add="+")
                haystack = " ".join([key["name"], key["label"]] + key["aliases"]).lower()
                chips.append((chip, key, haystack))
            self.groups.append((frame, chips, group["title"].lower(), columns))
            self._layout(chips, columns)

        # Everything that isn't a single named key
        extras = ctk.CTkFrame(self.body, fg_color="#2b2b2b", corner_radius=6)
        extras.pack(fill="x", padx=6, pady=(12, 8))
        self.extras = extras
        ctk.CTkLabel(
            extras,
            text="Combinations — join names with +, in any order:  ctrl+shift+s,  win+d,  alt+f4\n"
                 "Raw codes — any key without a name, as 🎯 Detect writes it:  vk0x5D  or  vk93\n"
                 "Fn — most keyboards never send Fn to Windows, so it has no name. Detect the "
                 "whole combination (e.g. Fn+F12) instead.",
            font=ctk.CTkFont(size=11), text_color="#aeb6bf", justify="left",
            wraplength=610, anchor="w"
        ).pack(anchor="w", padx=12, pady=10)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda e: self._close())

        if self.picking:
            # The dialog underneath is modal, so this window must take the grab
            # while it is open and hand it back afterwards
            self.after(50, self._take_grab)
        self.search_entry.focus_set()

    # --- layout / search --------------------------------------------------

    def _layout(self, chips, columns):
        for index, (chip, _, _) in enumerate(chips):
            chip.grid(row=index // columns, column=index % columns, padx=3, pady=3)

    def _schedule_filter(self, _event=None):
        if self._filter_id:
            self.after_cancel(self._filter_id)
        self._filter_id = self.after(120, self._apply_filter)

    def _apply_filter(self):
        self._filter_id = None
        query = self.search_entry.get().strip().lower()
        for frame, chips, title, columns in self.groups:
            # Keys that match by name, label or alias; failing that, a query
            # naming the group ("numpad", "browser") shows the whole group
            shown = [c for c in chips if not query or query in c[2]]
            if not shown and query and query in title:
                shown = chips
            for chip, _, _ in chips:
                chip.grid_remove()
            self._layout(shown, columns)
            if shown:
                frame.pack(fill="x", pady=(6, 2), before=self.extras)
            else:
                frame.pack_forget()
        self.after(60, self.body._refresh_scrollbar)

    # --- the info line ---------------------------------------------------

    def _show_default_info(self):
        self.info_label.configure(
            text="Point at a key to see what it is." + (
                "" if self.picking else "  Copied names can be pasted into any key field."
            )
        )

    def _show_info(self, key, usable=True):
        text = f"{key['name']}  —  {key['label']}"
        if key["aliases"]:
            text += "      also accepted: " + ", ".join(key["aliases"])
        if not usable:
            text += "      (mouse buttons can only be a source)"
        self.info_label.configure(text=text)

    # --- clicking keys -------------------------------------------------

    def _on_key(self, key):
        name = key["name"]
        if not self.picking:
            self.clipboard_clear()
            self.clipboard_append(name)
            self.info_label.configure(text=f"Copied “{name}” — paste it into any key field.")
            return

        parts = self._parts()
        if name not in parts:
            parts.append(name)
        self._write(parts)

    def _parts(self):
        return [part.strip() for part in self.entry.get().split('+') if part.strip()]

    def _write(self, parts):
        self.entry.delete(0, 'end')
        self.entry.insert(0, '+'.join(parts))
        self._refresh_current()

    def _remove_last(self):
        self._write(self._parts()[:-1])

    def _clear(self):
        self._write([])

    def _refresh_current(self):
        value = self.entry.get().strip()
        self.current_label.configure(text=value or "(nothing yet)")

    # --- window lifetime -----------------------------------------------

    def _take_grab(self):
        try:
            self.grab_set()
        except Exception:
            logger.debug("Could not take the grab for the key picker", exc_info=True)

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        parent = self.parent
        self.destroy()
        if self.picking and parent.winfo_exists():
            try:
                parent.grab_set()        # the dialog is modal again
            except Exception:
                pass
            self.entry.focus_set()
            self.entry.icursor('end')


class AddMappingDialog(ctk.CTkToplevel):
    """Dialog to add or edit a key mapping"""

    ACTION_LABELS = {
        "Send other key(s)": "keys",
        "Type text (ignores keyboard layout)": "text",
        "Launch a program or app": "launch",
        "Open a website": "url",
    }

    # Characters people most often want pinned to a key regardless of layout.
    # Punctuation first: it is what moves around between layouts.
    COMMON_CHARACTERS = [
        ("Period  .", "."),
        ("Comma  ,", ","),
        ("Semicolon  ;", ";"),
        ("Colon  :", ":"),
        ("Question mark  ?", "?"),
        ("Exclamation mark  !", "!"),
        ("Apostrophe  '", "'"),
        ("Quotation mark  \"", "\""),
        ("Slash  /", "/"),
        ("At sign  @", "@"),
        ("Hash  #", "#"),
        ("Em dash  —", "—"),
        ("Ellipsis  …", "…"),
        ("Euro  €", "€"),
        ("Degree  °", "°"),
    ]

    def __init__(self, parent, remapper: KeyRemapper, existing: dict = None):
        super().__init__(parent)
        self.editing = existing is not None
        self.title("Edit Key Mapping" if self.editing else "Add Key Mapping")
        # Tall enough for the common case, but the body scrolls - a laptop
        # screen must never hide the Add button. winfo_screenheight() is in
        # real pixels while geometry() is in scaled ones, hence the division.
        height = min(660, max(420, int(parent.winfo_screenheight() / _window_scaling(parent)) - 90))
        self.geometry(f"490x{height}")
        self.resizable(False, True)
        self.minsize(490, 380)
        self.transient(parent)
        self.grab_set()

        self.remapper = remapper
        self.result = None
        self.original = existing

        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 490) // 2
        y = max(0, parent.winfo_y() + (parent.winfo_height() - height) // 2)
        self.geometry(f"+{x}+{y}")

        # Buttons first, pinned to the bottom, so they survive any body height
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=14)

        ctk.CTkButton(
            btn_frame, text="Save" if self.editing else "Add", command=self._on_add, width=100
        ).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100).pack(side="left", padx=10)

        body = AutoHideScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=4, pady=(8, 0))
        self.body = body

        # Source key
        ctk.CTkLabel(body, text="Source Key (key to remap):", font=ctk.CTkFont(size=13)).pack(pady=(4, 4))
        source_frame = ctk.CTkFrame(body, fg_color="transparent")
        source_frame.pack(pady=4)
        self.source_entry = ctk.CTkEntry(source_frame, width=250, placeholder_text="e.g., capslock, ctrl+a, f1, mouse4")
        self.source_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(source_frame, text="🎯 Detect", command=self._detect_source, width=70).pack(side="left")
        self._keys_button(source_frame, self.source_entry, "Source key", allow_source_only=True)

        # What it does
        ctk.CTkLabel(body, text="What should it do?", font=ctk.CTkFont(size=13)).pack(pady=(14, 4))
        self.action_menu = ctk.CTkOptionMenu(
            body, values=list(self.ACTION_LABELS.keys()),
            command=self._on_action_change, width=365
        )
        self.action_menu.pack(pady=2)

        # --- Everything below swaps with the chosen action ---
        self.keys_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.value_frame = ctk.CTkFrame(body, fg_color="transparent")

        self.text_frame = ctk.CTkFrame(body, fg_color="transparent")

        self._build_keys_frame()
        self._build_text_frame()
        self._build_value_frame()

        # App scope
        self.scope_label = ctk.CTkLabel(body, text="Only in this app (optional):", font=ctk.CTkFont(size=13))
        self.scope_label.pack(pady=(12, 4))
        self.app_entry = ctk.CTkEntry(body, width=365, placeholder_text="e.g., game.exe (empty = everywhere)")
        self.app_entry.pack(pady=2)

        # Description
        self.desc_label = ctk.CTkLabel(body, text="Description (optional):", font=ctk.CTkFont(size=13))
        self.desc_label.pack(pady=(10, 4))
        self.desc_entry = ctk.CTkEntry(body, width=365, placeholder_text="e.g., Caps Lock to Escape")
        self.desc_entry.pack(pady=(2, 10))

        self._load_existing(existing)
        self.source_entry.focus()

    # --- the two interchangeable panels --------------------------------

    def _build_keys_frame(self):
        """Target keys, a picker of common ones, and the hold role."""
        frame = self.keys_frame

        ctk.CTkLabel(frame, text="Target Key (what it becomes):", font=ctk.CTkFont(size=13)).pack(pady=(12, 4))
        target_frame = ctk.CTkFrame(frame, fg_color="transparent")
        target_frame.pack(pady=2)
        self.target_entry = ctk.CTkEntry(target_frame, width=250, placeholder_text="e.g., escape, ctrl+c, mute, volumeup")
        self.target_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(target_frame, text="🎯 Detect", command=self._detect_target, width=70).pack(side="left")
        self._keys_button(target_frame, self.target_entry, "Target key", allow_source_only=False)

        # Ready-made targets - volume, media, function keys and friends
        picker = ctk.CTkFrame(frame, fg_color="transparent")
        picker.pack(pady=(6, 2))

        self._target_groups = {name: items for name, items in COMMON_TARGETS}
        self.target_group_menu = ctk.CTkOptionMenu(
            picker, values=list(self._target_groups), width=150,
            command=self._on_target_group_change, fg_color="#3b5a70", button_color="#2c5d7c"
        )
        self.target_group_menu.pack(side="left", padx=(0, 5))

        self.target_key_menu = ctk.CTkOptionMenu(
            picker, values=["—"], width=205, command=self._on_target_preset_change,
            fg_color="#3b5a70", button_color="#2c5d7c"
        )
        self.target_key_menu.pack(side="left")
        self._on_target_group_change(next(iter(self._target_groups)))

        # Hold role
        ctk.CTkLabel(frame, text="When held instead (optional):", font=ctk.CTkFont(size=13)).pack(pady=(12, 0))
        ctk.CTkLabel(
            frame, text="Single keys only — e.g. CapsLock taps Escape but acts as Ctrl when held",
            font=ctk.CTkFont(size=10), text_color="gray"
        ).pack(pady=(0, 4))
        hold_frame = ctk.CTkFrame(frame, fg_color="transparent")
        hold_frame.pack(pady=2)
        self.hold_entry = ctk.CTkEntry(hold_frame, width=250, placeholder_text="e.g., ctrl, shift (empty for none)")
        self.hold_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(hold_frame, text="🎯 Detect", command=self._detect_hold, width=70).pack(side="left")
        self._keys_button(hold_frame, self.hold_entry, "Hold key", allow_source_only=False)

    def _build_text_frame(self):
        """Literal characters, typed the same whatever the keyboard layout."""
        frame = self.text_frame

        ctk.CTkLabel(frame, text="Text to type:", font=ctk.CTkFont(size=13)).pack(pady=(12, 4))
        self.text_entry = ctk.CTkEntry(
            frame, width=365, placeholder_text="e.g.  .   or  ,   or  me@example.com"
        )
        self.text_entry.pack(pady=2)

        ctk.CTkLabel(
            frame, text="Or pick a character:", font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(pady=(8, 2))
        self._characters = dict(self.COMMON_CHARACTERS)
        self.char_preset_menu = ctk.CTkOptionMenu(
            frame, values=list(self._characters), width=365,
            command=self._on_char_preset_change,
            fg_color="#3b5a70", button_color="#2c5d7c"
        )
        self.char_preset_menu.set("Choose…")
        self.char_preset_menu.pack(pady=2)

        # Somewhere safe to see the result: the Test button types into here
        try_row = ctk.CTkFrame(frame, fg_color="transparent")
        try_row.pack(pady=(10, 2))
        self.try_entry = ctk.CTkEntry(try_row, width=285, placeholder_text="Test types here")
        self.try_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            try_row, text="▶ Test", command=self._test_text, width=75,
            fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left")

        ctk.CTkLabel(
            frame,
            text="Sent as characters, not keys, so switching keyboard layout does not "
                 "change them. Shift doesn't change them either, so add a separate rule "
                 "for the shifted character (e.g. rctrl → .  and  shift+rctrl → ,). "
                 "Games that read raw keyboard input won't see typed text.",
            font=ctk.CTkFont(size=10), text_color="gray", wraplength=400, justify="left"
        ).pack(pady=(6, 2))

        # Only shown while the master switch in Settings is off
        self.text_off_warning = ctk.CTkLabel(
            frame,
            text="Typing text is switched off in Settings. This rule will be saved "
                 "but won't do anything until you switch it back on.",
            font=ctk.CTkFont(size=11), text_color="#f39c12", wraplength=400, justify="left"
        )

    def _on_char_preset_change(self, label: str):
        char = self._characters.get(label)
        if char:
            self.text_entry.delete(0, 'end')
            self.text_entry.insert(0, char)

    def _test_text(self):
        text = self.text_entry.get()
        if not text:
            messagebox.showinfo("Nothing to test", "Fill in the text to type first.")
            return
        # Characters go wherever the keyboard focus is, so put it in the try box
        # and give Windows a moment to move it there before typing
        self.try_entry.delete(0, 'end')
        self.try_entry.focus_set()
        self.after(150, lambda: self.remapper.run_action("text", text))

    def _build_value_frame(self):
        """A program to launch, or a website to open."""
        frame = self.value_frame

        self.value_label = ctk.CTkLabel(frame, text="Program or app:", font=ctk.CTkFont(size=13))
        self.value_label.pack(pady=(12, 4))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(pady=2)
        self.value_entry = ctk.CTkEntry(row, width=225, placeholder_text=r"e.g., calc.exe or C:\Tools\thing.exe")
        self.value_entry.pack(side="left", padx=(0, 5))
        self.browse_btn = ctk.CTkButton(row, text="📂 Browse", command=self._browse_value, width=80)
        self.browse_btn.pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            row, text="▶ Test", command=self._test_value, width=70,
            fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left")

        self.app_preset_label = ctk.CTkLabel(
            frame, text="Or pick one:", font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.app_preset_label.pack(pady=(8, 2))

        self._app_commands = {name: command for name, command in COMMON_APPS}
        self.app_preset_menu = ctk.CTkOptionMenu(
            frame, values=list(self._app_commands), width=365,
            command=self._on_app_preset_change,
            fg_color="#3b5a70", button_color="#2c5d7c"
        )
        self.app_preset_menu.set("Calculator")
        self.app_preset_menu.pack(pady=2)

        self.value_hint = ctk.CTkLabel(
            frame,
            text="Store apps work too — paste a shell:AppsFolder\\… or ms-settings: link.",
            font=ctk.CTkFont(size=10), text_color="gray", wraplength=400
        )
        self.value_hint.pack(pady=(6, 2))

    # --- mode switching -------------------------------------------------

    def _current_action(self) -> str:
        return self.ACTION_LABELS.get(self.action_menu.get(), "keys")

    def _on_action_change(self, _label=None):
        action = self._current_action()

        self.keys_frame.pack_forget()
        self.text_frame.pack_forget()
        self.value_frame.pack_forget()

        if action == "keys":
            self.keys_frame.pack(before=self.scope_label, fill="x")
            self._refresh_body()
            return

        if action == "text":
            self.text_frame.pack(before=self.scope_label, fill="x")
            if self.remapper.settings.type_text_enabled:
                self.text_off_warning.pack_forget()
            else:
                self.text_off_warning.pack(pady=(6, 2))
            self._refresh_body()
            return

        self.value_frame.pack(before=self.scope_label, fill="x")
        self._refresh_body()
        if action == "launch":
            self.value_label.configure(text="Program or app:")
            self.value_entry.configure(placeholder_text=r"e.g., calc.exe or C:\Tools\thing.exe")
            self.browse_btn.configure(state="normal")
            self.app_preset_label.pack(pady=(8, 2))
            self.app_preset_menu.pack(pady=2)
            self.value_hint.configure(
                text="Store apps work too — paste a shell:AppsFolder\\… or ms-settings: link."
            )
        else:
            self.value_label.configure(text="Website:")
            self.value_entry.configure(placeholder_text="e.g., claude.ai")
            self.browse_btn.configure(state="disabled")
            self.app_preset_label.pack_forget()
            self.app_preset_menu.pack_forget()
            self.value_hint.configure(text="Opens in your default browser.")

    def _refresh_body(self):
        """The body grew or shrank, so the scrollbar may have to appear."""
        self.after(60, self.body._refresh_scrollbar)

    def _on_target_group_change(self, group: str):
        items = self._target_groups.get(group, [])
        labels = [label for label, _ in items] or ["—"]
        self.target_key_menu.configure(values=labels)
        self.target_key_menu.set(labels[0])

    def _on_target_preset_change(self, label: str):
        group = self._target_groups.get(self.target_group_menu.get(), [])
        value = next((v for name, v in group if name == label), None)
        if value:
            self.target_entry.delete(0, 'end')
            self.target_entry.insert(0, value)

    def _on_app_preset_change(self, name: str):
        command = self._app_commands.get(name)
        if command:
            self.value_entry.delete(0, 'end')
            self.value_entry.insert(0, command)

    def _browse_value(self):
        filepath = filedialog.askopenfilename(
            title="Choose a program or file",
            filetypes=[("Programs", "*.exe;*.bat;*.cmd;*.lnk"), ("All files", "*.*")]
        )
        if filepath:
            self.value_entry.delete(0, 'end')
            self.value_entry.insert(0, filepath)

    def _test_value(self):
        value = self.value_entry.get().strip()
        if not value:
            messagebox.showinfo("Nothing to test", "Fill in a program or website first.")
            return
        self.remapper.run_action(self._current_action(), value)

    # --- loading / saving ----------------------------------------------

    def _load_existing(self, existing: dict):
        if not existing:
            self._on_action_change()
            return

        action = existing.get('action', 'keys')
        self.action_menu.set(next(
            (label for label, value in self.ACTION_LABELS.items() if value == action),
            next(iter(self.ACTION_LABELS))
        ))
        self._on_action_change()

        self.source_entry.insert(0, existing.get('source', ''))
        self.target_entry.insert(0, existing.get('target', ''))
        self.hold_entry.insert(0, existing.get('hold', ''))
        if action == "text":
            self.text_entry.insert(0, existing.get('value', ''))
        else:
            self.value_entry.insert(0, existing.get('value', ''))
        self.app_entry.insert(0, existing.get('app', ''))

        # Only carry over a description the user actually wrote - an
        # auto-generated "x -> y" would go stale the moment they edit
        description = existing.get('description', '')
        auto = f"{existing.get('source', '')} -> " \
               f"{existing.get('value') or existing.get('target', '')}".lower()
        if description.lower() != auto:
            self.desc_entry.insert(0, description)

    def _detect_into(self, entry, title):
        dialog = KeyCaptureDialog(self, title)
        self.wait_window(dialog)
        if dialog.result:
            entry.delete(0, 'end')
            entry.insert(0, dialog.result)

    def _keys_button(self, row, entry, field_name, allow_source_only):
        """The ⌨ button: browse every key name and click to fill the field."""
        ctk.CTkButton(
            row, text="⌨", width=36, font=ctk.CTkFont(size=16),
            fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER,
            command=lambda: KeyReferenceWindow(
                self, entry=entry, field_name=field_name,
                allow_source_only=allow_source_only
            )
        ).pack(side="left", padx=(5, 0))

    def _detect_source(self):
        """Open key detection dialog for source key"""
        self._detect_into(self.source_entry, "Detect Source Key")

    def _detect_target(self):
        """Open key detection dialog for target key"""
        self._detect_into(self.target_entry, "Detect Target Key")

    def _detect_hold(self):
        """Open key detection dialog for the hold role"""
        self._detect_into(self.hold_entry, "Detect Hold Key")

    def _on_add(self):
        action = self._current_action()
        source = self.source_entry.get().strip()
        target = self.target_entry.get().strip() if action == "keys" else ""
        hold = self.hold_entry.get().strip() if action == "keys" else ""
        if action == "text":
            # Deliberately not stripped: ", " and a lone space are real text
            value = self.text_entry.get()
        elif action != "keys":
            value = self.value_entry.get().strip()
        else:
            value = ""
        app = self.app_entry.get().strip()
        desc = self.desc_entry.get().strip()

        if not source:
            messagebox.showerror("Error", "Please enter a source key.")
            return
        if action == "keys" and not target:
            messagebox.showerror("Error", "Please enter a target key.")
            return
        if action != "keys" and not value:
            messagebox.showerror("Error", {
                "text": "Please enter the text to type.",
                "launch": "Please choose a program to launch.",
            }.get(action, "Please enter a website address."))
            return

        ignore = None
        if self.editing:
            try:
                ignore = (self.remapper.parse_key_string(self.original['source']),
                          self.remapper.normalize_app(self.original.get('app', '')))
            except ValueError:
                ignore = None

        conflict = self.remapper.find_conflict(source, app, ignore=ignore)
        if conflict and not messagebox.askyesno(
            "Conflict",
            f"{conflict}.\n\nReplace the existing rule?"
        ):
            return

        if self.editing:
            self.remapper.remove_mapping(self.original['source'], self.original.get('app', ''))

        if self.remapper.add_mapping(source, target, desc, hold=hold, app=app,
                                     action=action, value=value):
            self.result = (source, target or value, desc)
            self.destroy()
        else:
            if self.editing:
                # Put the rule we just removed back
                self.remapper.add_mapping(
                    self.original['source'], self.original['target'],
                    self.original.get('description', ''),
                    hold=self.original.get('hold', ''), app=self.original.get('app', ''),
                    action=self.original.get('action', 'keys'),
                    value=self.original.get('value', ''),
                )
            messagebox.showerror(
                "Error",
                "Could not create that mapping.\n\n"
                "Check the key names (see 📋 Show Keys). Hold actions only work\n"
                "on single keys, and only when the mapping sends keys."
            )


class BlockKeyDialog(ctk.CTkToplevel):
    """Dialog to block a key"""
    
    def __init__(self, parent, remapper: KeyRemapper):
        super().__init__(parent)
        self.title("Block Key")
        self.geometry("400x360")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.remapper = remapper
        self.result = None
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 280) // 2
        self.geometry(f"+{x}+{y}")
        
        # Info
        ctk.CTkLabel(
            self, 
            text="Block a key to completely disable it.\nUseful for preventing accidental presses in games.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        ).pack(pady=(15, 10))
        
        # Key to block
        ctk.CTkLabel(self, text="Key to Block:", font=ctk.CTkFont(size=13)).pack(pady=(10, 5))
        key_frame = ctk.CTkFrame(self, fg_color="transparent")
        key_frame.pack(pady=5)
        self.key_entry = ctk.CTkEntry(key_frame, width=200, placeholder_text="e.g., /, win, alt+tab, f1")
        self.key_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(key_frame, text="🎯 Detect", command=self._detect_key, width=60).pack(side="left")
        ctk.CTkButton(
            key_frame, text="⌨", width=36, font=ctk.CTkFont(size=16),
            fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER,
            command=lambda: KeyReferenceWindow(self, entry=self.key_entry, field_name="Key to block")
        ).pack(side="left", padx=(5, 0))
        
        # App scope
        ctk.CTkLabel(self, text="Only in this app (optional):", font=ctk.CTkFont(size=13)).pack(pady=(10, 4))
        self.app_entry = ctk.CTkEntry(self, width=300, placeholder_text="e.g., game.exe (empty = everywhere)")
        self.app_entry.pack(pady=2)

        # Description
        ctk.CTkLabel(self, text="Description (optional):", font=ctk.CTkFont(size=13)).pack(pady=(10, 4))
        self.desc_entry = ctk.CTkEntry(self, width=300, placeholder_text="e.g., Block chat key in games")
        self.desc_entry.pack(pady=2)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        ctk.CTkButton(btn_frame, text="Block", command=self._on_block, width=100, fg_color="#c0392b", hover_color="#e74c3c").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100).pack(side="left", padx=10)
        
        self.key_entry.focus()
    
    def _detect_key(self):
        """Open key detection dialog"""
        dialog = KeyCaptureDialog(self, "Detect Key to Block")
        self.wait_window(dialog)
        if dialog.result:
            self.key_entry.delete(0, 'end')
            self.key_entry.insert(0, dialog.result)
    
    def _on_block(self):
        key = self.key_entry.get().strip()
        desc = self.desc_entry.get().strip()
        app = self.app_entry.get().strip()

        if not key:
            messagebox.showerror("Error", "Please enter a key to block.")
            return

        conflict = self.remapper.find_conflict(key, app)
        if conflict and not messagebox.askyesno(
            "Conflict", f"{conflict}.\n\nBlock it anyway? The block wins."
        ):
            return

        if self.remapper.block_key(key, desc, app=app):
            self.result = (key, desc)
            self.destroy()
        else:
            messagebox.showerror("Error", f"Invalid key name: '{key}'")


class KeyRemapperGUI(UiQueueMixin, ctk.CTk):
    """Main GUI Application"""

    def __init__(self, start_minimized: bool = False):
        super().__init__()

        self.title("Key Remapper - Gaming Edition")
        self.geometry("760x640")
        self.minsize(640, 540)
        self.tray_icon = None
        # The tray icon is easy to miss - Windows 11 hides new ones in the
        # overflow menu - so say so once per run rather than looking like a crash
        self._tray_announced = False
        self._init_ui_queue()

        # Initialize remapper
        self.remapper = KeyRemapper()
        self.remapper.load_config()
        self.remapper.on_pause_changed = self._on_pause_changed

        # Build UI
        self._create_ui()
        self._refresh_lists()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Startup behaviour
        if self.remapper.settings.start_on_launch and self.remapper.has_work():
            if self.remapper.start():
                self._update_status(True)

        if start_minimized or self.remapper.settings.start_minimized:
            self.after(200, self._minimize_to_tray)
    
    def _create_ui(self):
        """Create the main UI"""
        
        # Top frame - Status and controls
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        # Status indicator
        self.status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        self.status_frame.pack(side="left", padx=10)
        
        self.status_indicator = ctk.CTkLabel(
            self.status_frame, 
            text="●", 
            font=ctk.CTkFont(size=24),
            text_color="#e74c3c"
        )
        self.status_indicator.pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text="STOPPED", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.status_label.pack(side="left", padx=(5, 0))
        
        # Control buttons
        btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)
        
        self.start_btn = ctk.CTkButton(
            btn_frame, 
            text="▶ Start", 
            command=self._start_remapper,
            width=100,
            fg_color=START_COLOR,
            hover_color=START_HOVER,
            text_color_disabled=IDLE_TEXT
        )
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame, 
            text="■ Stop", 
            command=self._stop_remapper,
            width=100,
            fg_color=STOP_IDLE,
            hover_color=STOP_HOVER,
            text_color_disabled=IDLE_TEXT,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        # Tabview for mappings and blocked keys
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.tab_mappings = self.tabview.add("Key Mappings")
        self.tab_blocked = self.tabview.add("Blocked Keys")
        self.tab_copilot = self.tabview.add("Copilot Key")
        self.tab_settings = self.tabview.add("Settings")

        # === Mappings Tab ===
        self._create_mappings_tab()

        # === Blocked Keys Tab ===
        self._create_blocked_tab()

        # === Copilot Key Tab ===
        self._create_copilot_tab()

        # === Settings Tab ===
        self._create_settings_tab()

        # Bottom frame - Save/Load
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkButton(
            bottom_frame, 
            text="💾 Save Config", 
            command=self._save_config,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            bottom_frame, 
            text="📂 Load Config", 
            command=self._load_config,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            bottom_frame, 
            text="📋 Show Keys", 
            command=self._show_available_keys,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            bottom_frame, 
            text="ℹ️ About", 
            command=self._show_about,
            width=100
        ).pack(side="left", padx=5)
        
        # Config file path
        self.config_label = ctk.CTkLabel(
            bottom_frame, 
            text=f"Config: {CONFIG_FILE.name}",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.config_label.pack(side="right", padx=10)
    
    def _create_mappings_tab(self):
        """Create the mappings tab content"""
        
        # Toolbar
        toolbar = ctk.CTkFrame(self.tab_mappings, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(
            toolbar, 
            text="+ Add Mapping", 
            command=self._add_mapping,
            width=130
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="Edit Selected",
            command=self._edit_mapping,
            width=130,
            fg_color=GRAY_BUTTON,
            hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="Remove Selected",
            command=self._remove_mapping,
            width=130,
            fg_color=GRAY_BUTTON,
            hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="Toggle On/Off",
            command=self._toggle_mapping,
            width=130,
            fg_color=GRAY_BUTTON,
            hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            self.tab_mappings,
            text="Double-click a row to edit it.",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", pady=(0, 4))

        # Scrollable frame for mappings
        self.mappings_frame = AutoHideScrollableFrame(self.tab_mappings)
        self.mappings_frame.pack(fill="both", expand=True)

        # Header
        header = ctk.CTkFrame(self.mappings_frame, fg_color="#2b2b2b", corner_radius=5)
        header.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(header, text="", width=30).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Source", width=110, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="→", width=20).pack(side="left")
        ctk.CTkLabel(header, text="Target", width=110, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Hold", width=70, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="App", width=90, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Description", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)

        self.mapping_widgets = []
        self.selected_mapping = None
    
    def _create_blocked_tab(self):
        """Create the blocked keys tab content"""
        
        # Info label
        info_label = ctk.CTkLabel(
            self.tab_blocked,
            text="Blocked keys are completely disabled - useful for preventing accidental key presses during gaming.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        info_label.pack(pady=(0, 10))
        
        # Toolbar
        toolbar = ctk.CTkFrame(self.tab_blocked, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(
            toolbar, 
            text="+ Block Key", 
            command=self._block_key,
            width=130,
            fg_color="#c0392b",
            hover_color="#e74c3c"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, 
            text="Unblock Selected", 
            command=self._unblock_key,
            width=130,
            fg_color=GRAY_BUTTON,
            hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, 
            text="Toggle On/Off", 
            command=self._toggle_blocked,
            width=130,
            fg_color=GRAY_BUTTON,
            hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=5)
        
        # Scrollable frame for blocked keys
        self.blocked_frame = AutoHideScrollableFrame(self.tab_blocked)
        self.blocked_frame.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(self.blocked_frame, fg_color="#2b2b2b", corner_radius=5)
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header, text="", width=30).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Key", width=150, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="App", width=90, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Description", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        
        self.blocked_widgets = []
        self.selected_blocked = None
    
    # ------------------------------------------------------------------
    # Copilot key tab
    # ------------------------------------------------------------------

    COPILOT_MODE_LABELS = {
        "Do nothing — disable the key": "disable",
        "Send other key(s) instead": "keys",
        "Launch a program or file": "launch",
        "Open a website": "url",
        "Leave it alone (pass through)": "passthrough",
    }

    # Turn the Copilot key back into the key it displaced. These are the four
    # keys OEMs most often sacrificed to make room for it.
    COPILOT_KEY_PRESETS = [
        ("Right Alt", "ralt"),
        ("Windows", "rwin"),
        ("Menu ▤", "apps"),
        ("Right Ctrl", "rctrl"),
    ]

    COPILOT_PRESETS = [
        ("🚫 Disable it", "disable", ""),
        ("✂️ Screenshot", "keys", "win+shift+s"),
        ("⏯️ Play / Pause", "keys", "playpause"),
        ("🗂️ File Explorer", "launch", "explorer.exe"),
    ]

    def _create_copilot_tab(self):
        """Create the Copilot key tab content"""
        tab = AutoHideScrollableFrame(self.tab_copilot)
        tab.pack(fill="both", expand=True)

        copilot = self.remapper.copilot
        self._copilot_modifiers = copilot.modifiers
        self._copilot_key = copilot.key or DEFAULT_COPILOT_KEY

        ctk.CTkLabel(
            tab,
            text="The Copilot key has no scan code of its own — the keyboard firmware\n"
                 "sends a hidden shortcut. Detect it once, then give it any job you like.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="left"
        ).pack(pady=(5, 12), anchor="w", padx=10)

        # --- Which chord does this laptop send? ---
        chord_box = ctk.CTkFrame(tab)
        chord_box.pack(fill="x", padx=10, pady=(0, 12))

        ctk.CTkLabel(
            chord_box, text="Your Copilot key sends", font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(side="left", padx=(12, 8), pady=12)

        self.copilot_chord_label = ctk.CTkLabel(
            chord_box, text=copilot.chord_text(), font=ctk.CTkFont(size=15, weight="bold")
        )
        self.copilot_chord_label.pack(side="left", pady=12)

        ctk.CTkButton(
            chord_box, text="🎯 Detect", command=self._detect_copilot_key, width=90
        ).pack(side="right", padx=12, pady=12)

        # --- Turn it back into a normal key ---
        ctk.CTkLabel(
            tab, text="Make it a normal key again", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)

        ctk.CTkLabel(
            tab,
            text="One click to give back whichever key your laptop gave up for Copilot.",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        key_preset_frame = ctk.CTkFrame(tab, fg_color="transparent")
        key_preset_frame.pack(fill="x", padx=6, pady=(0, 14))

        for label, value in self.COPILOT_KEY_PRESETS:
            ctk.CTkButton(
                key_preset_frame,
                text=label,
                width=150,
                fg_color="#2c5d7c",
                hover_color="#3d7ca3",
                command=lambda v=value: self._apply_copilot_preset("keys", v)
            ).pack(side="left", padx=4)

        # --- Quick presets ---
        ctk.CTkLabel(
            tab, text="Other quick presets", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)

        preset_frame = ctk.CTkFrame(tab, fg_color="transparent")
        preset_frame.pack(fill="x", padx=6, pady=(4, 14))

        for label, mode, value in self.COPILOT_PRESETS:
            ctk.CTkButton(
                preset_frame,
                text=label,
                width=150,
                fg_color="#34495e",
                hover_color="#4a6580",
                command=lambda m=mode, v=value: self._apply_copilot_preset(m, v)
            ).pack(side="left", padx=4)

        # --- Custom action ---
        ctk.CTkLabel(
            tab, text="When I press the Copilot key…", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)

        self.copilot_mode_menu = ctk.CTkOptionMenu(
            tab,
            values=list(self.COPILOT_MODE_LABELS.keys()),
            command=self._on_copilot_mode_change,
            width=320
        )
        self.copilot_mode_menu.pack(anchor="w", padx=10, pady=(6, 8))

        self.copilot_value_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.copilot_value_frame.pack(fill="x", padx=6)

        self.copilot_value_entry = ctk.CTkEntry(self.copilot_value_frame, width=330)
        self.copilot_value_entry.pack(side="left", padx=(4, 5))

        self.copilot_value_btn = ctk.CTkButton(
            self.copilot_value_frame, text="🎯 Detect", width=90, command=self._pick_copilot_value
        )
        self.copilot_value_btn.pack(side="left")

        # --- Apply / test ---
        action_frame = ctk.CTkFrame(tab, fg_color="transparent")
        action_frame.pack(fill="x", padx=6, pady=(14, 4))

        ctk.CTkButton(
            action_frame, text="✔ Apply", command=self._apply_copilot, width=120,
            fg_color="#27ae60", hover_color="#2ecc71"
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            action_frame, text="▶ Test action", command=self._test_copilot, width=120,
            fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=4)

        self.copilot_status_label = ctk.CTkLabel(
            tab, text="", font=ctk.CTkFont(size=12), text_color="gray",
            justify="left", wraplength=560
        )
        self.copilot_status_label.pack(anchor="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            tab,
            text="Note: the remapper must be running (▶ Start) for this to take effect.\n"
                 "Modifier targets (Alt/Ctrl/Win/Menu) are held for as long as the firmware\n"
                 "holds the chord — most keyboards send it as a single tap.\n"
                 "Windows 11 24H2 can also remap this key in Settings, but only to signed,\n"
                 "packaged apps — this works with anything.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        ).pack(anchor="w", padx=10, pady=(6, 10))

        self._refresh_copilot()

    def _copilot_label_for_mode(self, mode: str) -> str:
        for label, value in self.COPILOT_MODE_LABELS.items():
            if value == mode:
                return label
        return next(iter(self.COPILOT_MODE_LABELS))

    def _refresh_copilot(self):
        """Sync the Copilot widgets with the remapper's current configuration"""
        copilot = self.remapper.copilot
        self._copilot_modifiers = copilot.modifiers
        self._copilot_key = copilot.key or DEFAULT_COPILOT_KEY

        self.copilot_chord_label.configure(text=copilot.chord_text())
        mode = copilot.mode if copilot.enabled else "passthrough"
        self.copilot_mode_menu.set(self._copilot_label_for_mode(mode))

        self.copilot_value_entry.delete(0, 'end')
        if copilot.value:
            self.copilot_value_entry.insert(0, copilot.value)

        self._on_copilot_mode_change(self.copilot_mode_menu.get())
        self.copilot_status_label.configure(
            text=f"Current: {copilot.action_text()}" if copilot.enabled
            else "Current: the Copilot key is left untouched.",
            text_color="#27ae60" if copilot.enabled else "gray"
        )

    def _on_copilot_mode_change(self, label: str):
        """Show the right input for the selected action"""
        mode = self.COPILOT_MODE_LABELS.get(label, "disable")

        if mode == "keys":
            self.copilot_value_frame.pack(fill="x", padx=6)
            self.copilot_value_entry.configure(placeholder_text="e.g. ctrl+shift+p, playpause, f13")
            self.copilot_value_btn.configure(text="🎯 Detect", state="normal")
        elif mode == "launch":
            self.copilot_value_frame.pack(fill="x", padx=6)
            self.copilot_value_entry.configure(placeholder_text=r"e.g. C:\Windows\notepad.exe")
            self.copilot_value_btn.configure(text="📂 Browse", state="normal")
        elif mode == "url":
            self.copilot_value_frame.pack(fill="x", padx=6)
            self.copilot_value_entry.configure(placeholder_text="e.g. https://claude.ai")
            self.copilot_value_btn.configure(text="—", state="disabled")
        else:
            self.copilot_value_frame.pack_forget()

    def _pick_copilot_value(self):
        """Detect a key combo or browse for a program, depending on the mode"""
        mode = self.COPILOT_MODE_LABELS.get(self.copilot_mode_menu.get(), "disable")

        if mode == "keys":
            dialog = KeyCaptureDialog(self, "Detect Replacement Key")
            self.wait_window(dialog)
            if dialog.result:
                self.copilot_value_entry.delete(0, 'end')
                self.copilot_value_entry.insert(0, dialog.result)
        elif mode == "launch":
            filepath = filedialog.askopenfilename(
                title="Choose a program or file",
                filetypes=[("Programs", "*.exe;*.bat;*.cmd;*.lnk"), ("All files", "*.*")]
            )
            if filepath:
                self.copilot_value_entry.delete(0, 'end')
                self.copilot_value_entry.insert(0, filepath)

    def _apply_copilot_preset(self, mode: str, value: str):
        self.copilot_mode_menu.set(self._copilot_label_for_mode(mode))
        self._on_copilot_mode_change(self.copilot_mode_menu.get())
        self.copilot_value_entry.delete(0, 'end')
        if value:
            self.copilot_value_entry.insert(0, value)
        self._apply_copilot()

    def _apply_copilot(self):
        """Save the Copilot key configuration (takes effect immediately)"""
        mode = self.COPILOT_MODE_LABELS.get(self.copilot_mode_menu.get(), "disable")
        value = self.copilot_value_entry.get().strip()

        config = CopilotConfig(
            enabled=(mode != "passthrough"),
            modifiers=tuple(self._copilot_modifiers),
            key=self._copilot_key,
            mode=mode,
            value=value,
            description="Copilot key",
        )

        if not self.remapper.set_copilot(config):
            if mode == "keys":
                messagebox.showerror("Error", f"'{value}' is not a key name I recognise.\n"
                                              "Use the 🎯 Detect button or see 📋 Show Keys.")
            else:
                messagebox.showerror("Error", "Please fill in a program or URL first.")
            return

        self.remapper.save_config()
        self._refresh_copilot()

    def _test_copilot(self):
        """Run the configured action without pressing the key"""
        self._apply_copilot()
        if self.remapper.copilot.mode in ("disable", "passthrough"):
            messagebox.showinfo("Nothing to test", "This action does not do anything visible.")
            return
        self.remapper.run_copilot_action()

    def _detect_copilot_key(self):
        """Capture the chord this laptop's Copilot key actually sends"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Detect Copilot Key")
        dialog.geometry("430x210")
        dialog.resizable(False, False)
        dialog.transient(self)

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 430) // 2
        y = self.winfo_y() + (self.winfo_height() - 210) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="Press your Copilot key now",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(25, 10))

        ctk.CTkLabel(
            dialog,
            text="Every keystroke is intercepted until you do.\n"
                 "Press Escape (or click Cancel) to stop.",
            font=ctk.CTkFont(size=12), text_color="gray", justify="center"
        ).pack(pady=5)

        def cancel():
            self.remapper.cancel_capture()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Cancel", command=cancel, width=110).pack(pady=15)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.grab_set()

        def on_chord(chord):
            # Called on the hook thread - hand back to the UI thread
            self.post_to_ui(lambda: self._finish_copilot_detect(dialog, chord))

        if not self.remapper.start_capture(on_chord):
            dialog.destroy()
            messagebox.showerror(
                "Error",
                "Could not start key detection.\nAnother capture may already be running."
            )

    def _finish_copilot_detect(self, dialog, chord):
        if dialog.winfo_exists():
            dialog.destroy()

        if not chord:
            return

        self._copilot_modifiers = chord.modifiers
        self._copilot_key = chord.vk
        self._apply_copilot()

        managed = self.remapper.copilot.enabled
        messagebox.showinfo(
            "Copilot Key Detected",
            f"Your Copilot key sends:\n\n{self.remapper.copilot.chord_text()}\n"
            f"({chord.hardware_text()})\n\n" +
            ("It is now managed by Key Remapper."
             if managed else
             "Now pick what it should do below and click Apply.")
        )

    # ------------------------------------------------------------------
    # Settings tab
    # ------------------------------------------------------------------

    def _create_settings_tab(self):
        """Create the settings tab content"""
        tab = AutoHideScrollableFrame(self.tab_settings)
        tab.pack(fill="both", expand=True)

        settings = self.remapper.settings

        # --- Pause hotkey ---
        ctk.CTkLabel(
            tab, text="Pause / resume hotkey", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10, pady=(6, 0))
        ctk.CTkLabel(
            tab,
            text="Suspends every mapping without stopping the remapper — handy when a\n"
                 "remapped key is fighting with an application.",
            font=ctk.CTkFont(size=11), text_color="gray", justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        hotkey_frame = ctk.CTkFrame(tab, fg_color="transparent")
        hotkey_frame.pack(fill="x", padx=6, pady=(0, 14))

        self.hotkey_entry = ctk.CTkEntry(
            hotkey_frame, width=250, placeholder_text="e.g. ctrl+alt+f12 (empty = none)"
        )
        self.hotkey_entry.pack(side="left", padx=(4, 5))
        if settings.toggle_hotkey:
            self.hotkey_entry.insert(0, settings.toggle_hotkey)

        ctk.CTkButton(
            hotkey_frame, text="🎯 Detect", width=90,
            command=lambda: self._detect_into_entry(self.hotkey_entry, "Detect Pause Hotkey")
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            hotkey_frame, text="Clear", width=70, fg_color=GRAY_BUTTON, hover_color=GRAY_BUTTON_HOVER,
            command=lambda: self.hotkey_entry.delete(0, 'end')
        ).pack(side="left")

        # --- Tap timeout ---
        ctk.CTkLabel(
            tab, text="Tap vs hold threshold", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)
        ctk.CTkLabel(
            tab,
            text="How long a dual-role key must be down before it counts as held.",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        timeout_frame = ctk.CTkFrame(tab, fg_color="transparent")
        timeout_frame.pack(fill="x", padx=6, pady=(0, 14))

        self.timeout_slider = ctk.CTkSlider(
            timeout_frame, from_=50, to=1000, number_of_steps=19, width=300,
            command=self._on_timeout_slide
        )
        self.timeout_slider.set(settings.tap_timeout_ms)
        self.timeout_slider.pack(side="left", padx=(4, 10))

        self.timeout_label = ctk.CTkLabel(timeout_frame, text=f"{settings.tap_timeout_ms} ms", width=70)
        self.timeout_label.pack(side="left")

        # --- Startup behaviour ---
        ctk.CTkLabel(
            tab, text="Startup", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)

        self.startup_var = ctk.BooleanVar(value=is_run_at_startup())
        ctk.CTkCheckBox(
            tab, text="Launch Key Remapper when I sign in",
            variable=self.startup_var
        ).pack(anchor="w", padx=14, pady=4)

        self.minimized_var = ctk.BooleanVar(value=settings.start_minimized)
        ctk.CTkCheckBox(
            tab, text="Start hidden in the system tray",
            variable=self.minimized_var
        ).pack(anchor="w", padx=14, pady=4)

        self.autostart_var = ctk.BooleanVar(value=settings.start_on_launch)
        ctk.CTkCheckBox(
            tab, text="Activate my mappings as soon as the app opens",
            variable=self.autostart_var
        ).pack(anchor="w", padx=14, pady=(4, 14))

        # --- Typing text ---
        ctk.CTkLabel(
            tab, text="Typing text", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)
        ctk.CTkLabel(
            tab,
            text="\u201cType text\u201d rules send characters instead of keys, so switching\n"
                 "keyboard layout never changes what they type. Untick to pause every\n"
                 "text rule at once \u2014 the keys go back to normal, and the rules are kept.",
            font=ctk.CTkFont(size=11), text_color="gray", justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        self.type_text_var = ctk.BooleanVar(value=settings.type_text_enabled)
        ctk.CTkCheckBox(
            tab, text="Type text as characters (layout-independent)",
            variable=self.type_text_var
        ).pack(anchor="w", padx=14, pady=(4, 14))

        # --- Gaming: numpad + Shift ---
        ctk.CTkLabel(
            tab, text="Gaming", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10)
        ctk.CTkLabel(
            tab,
            text="With NumLock on, Windows turns Shift+Numpad into arrow keys and briefly\n"
                 "lets go of Shift \u2014 so a numpad binding misfires and a held Shift (sprint,\n"
                 "crouch) drops for an instant. This keeps the numpad sending numbers and\n"
                 "Shift held. Real arrow keys, and the numpad with NumLock off, are unaffected.",
            font=ctk.CTkFont(size=11), text_color="gray", justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        self.numpad_var = ctk.BooleanVar(value=settings.numpad_ignores_shift)
        ctk.CTkCheckBox(
            tab, text="Keep numpad keys as numbers while Shift is held",
            variable=self.numpad_var, command=self._on_numpad_toggled
        ).pack(anchor="w", padx=14, pady=4)

        # Always visible, not just in the popup: the limits are the first thing
        # to check when it seems not to work in a particular game
        admin = check_admin()
        ctk.CTkLabel(
            tab,
            text="\u26a0 Most games run as administrator, and Windows only lets Key Remapper\n"
                 "change their input when it runs as administrator too. Some games and\n"
                 "anti-cheat systems block it regardless.",
            font=ctk.CTkFont(size=11), text_color="#f39c12", justify="left"
        ).pack(anchor="w", padx=14, pady=(2, 2))
        ctk.CTkLabel(
            tab,
            text=("\u2714 Key Remapper is running as administrator." if admin else
                  "\u2716 Key Remapper is NOT running as administrator right now."),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#27ae60" if admin else "#e74c3c", justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 14))

        # --- Apply ---
        ctk.CTkButton(
            tab, text="✔ Apply", command=self._apply_settings, width=120,
            fg_color="#27ae60", hover_color="#2ecc71"
        ).pack(anchor="w", padx=10)

        self.settings_status_label = ctk.CTkLabel(
            tab, text="", font=ctk.CTkFont(size=12), text_color="gray", justify="left"
        )
        self.settings_status_label.pack(anchor="w", padx=10, pady=(8, 4))

        # --- Reset ---
        ctk.CTkLabel(
            tab, text="Start over", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10, pady=(14, 0))
        ctk.CTkLabel(
            tab,
            text="Removes every mapping, blocked key and Copilot action, and puts all\n"
                 "settings back to their defaults.",
            font=ctk.CTkFont(size=11), text_color="gray", justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        ctk.CTkButton(
            tab, text="↺ Reset everything to defaults", command=self._reset_all, width=230,
            fg_color="#c0392b", hover_color="#e74c3c"
        ).pack(anchor="w", padx=10, pady=(0, 12))

        ctk.CTkLabel(
            tab,
            text=f"Settings and log: {CONFIG_DIR}",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", padx=10, pady=(10, 6))

    def _on_numpad_toggled(self):
        """Warn when the numpad option is switched on - before anyone relies on it."""
        if not self.numpad_var.get():
            return
        admin = check_admin()
        messagebox.showwarning(
            "Before you rely on this in a game",
            "This works by intercepting the keyboard, and Windows only allows that "
            "for a game when Key Remapper has at least the same permissions.\n\n"
            "\u2022 Most games run as administrator, so Key Remapper must run as "
            "administrator too: close it, right-click KeyRemapper.exe and choose "
            "\u201cRun as administrator\u201d.\n\n"
            "\u2022 Some games and anti-cheat systems block keyboard hooks entirely. "
            "There, this option cannot work, whatever the permissions.\n\n"
            + ("Key Remapper is running as administrator right now."
               if admin else
               "Key Remapper is NOT running as administrator right now.")
            + "\n\nClick \u2714 Apply to turn it on, then \u25b6 Start."
        )

    def _detect_into_entry(self, entry, title):
        dialog = KeyCaptureDialog(self, title)
        self.wait_window(dialog)
        if dialog.result:
            entry.delete(0, 'end')
            entry.insert(0, dialog.result)

    def _on_timeout_slide(self, value):
        self.timeout_label.configure(text=f"{int(value)} ms")

    def _apply_settings(self):
        """Validate and store the global settings"""
        settings = Settings(
            toggle_hotkey=self.hotkey_entry.get().strip(),
            tap_timeout_ms=int(self.timeout_slider.get()),
            run_at_startup=bool(self.startup_var.get()),
            start_minimized=bool(self.minimized_var.get()),
            start_on_launch=bool(self.autostart_var.get()),
            type_text_enabled=bool(self.type_text_var.get()),
            numpad_ignores_shift=bool(self.numpad_var.get()),
        )

        if not self.remapper.apply_settings(settings):
            messagebox.showerror(
                "Error",
                f"'{settings.toggle_hotkey}' is not a key combination I recognise.\n"
                "Use the 🎯 Detect button or see 📋 Show Keys."
            )
            return

        if not set_run_at_startup(settings.run_at_startup, settings.start_minimized):
            messagebox.showwarning(
                "Warning", "Settings saved, but the run-at-startup entry could not be updated."
            )

        self.remapper.save_config()
        self._refresh_mappings()
        self.settings_status_label.configure(
            text="Saved. " + (f"Press {settings.toggle_hotkey} to pause or resume."
                              if settings.toggle_hotkey else "No pause hotkey set."),
            text_color="#27ae60"
        )

    def _refresh_settings_widgets(self):
        """
        Make the Settings tab show what the remapper actually has.

        Needed after Reset and after Load: otherwise the tab keeps showing the
        old values, and the next Apply quietly writes them back.
        """
        settings = self.remapper.settings
        self.hotkey_entry.delete(0, 'end')
        if settings.toggle_hotkey:
            self.hotkey_entry.insert(0, settings.toggle_hotkey)
        self.timeout_slider.set(settings.tap_timeout_ms)
        self._on_timeout_slide(settings.tap_timeout_ms)
        self.startup_var.set(is_run_at_startup())      # lives in the registry
        self.minimized_var.set(settings.start_minimized)
        self.autostart_var.set(settings.start_on_launch)
        self.type_text_var.set(settings.type_text_enabled)
        self.numpad_var.set(settings.numpad_ignores_shift)

    def _reset_all(self):
        """Wipe every rule and setting after confirming"""
        counts = (f"{len(self.remapper.mappings)} mapping(s), "
                  f"{len(self.remapper.blocked_keys)} blocked key(s)")

        if not messagebox.askyesno(
            "Reset everything?",
            f"This deletes {counts}, clears the Copilot key action and puts every\n"
            "setting back to its default.\n\n"
            "A backup of your current setup is saved first, so you can bring it back\n"
            "with \U0001f4c2 Load Config. Continue?",
            icon="warning"
        ):
            return

        backup = self.remapper.backup_config("reset")
        if backup is None and not messagebox.askyesno(
            "Backup failed",
            "Your current setup could not be backed up.\n\nReset anyway? It cannot be undone.",
            icon="warning"
        ):
            return

        was_running = self.remapper.running
        self.remapper.stop()
        self.remapper.reset_to_defaults()

        # The logon entry lives in the registry, not the config file
        set_run_at_startup(False)

        self.remapper.save_config()

        self._refresh_settings_widgets()
        self.settings_status_label.configure(text="Everything reset to defaults.", text_color="gray")

        self._refresh_lists()
        self._update_status(self.remapper.running)

        messagebox.showinfo(
            "Reset",
            "Everything is back to defaults."
            + ("\n\nThe remapper was stopped because there are no rules left to apply."
               if was_running else "")
            + (f"\n\nYour previous setup was backed up to:\n{backup}\n\n"
               "Use \U0001f4c2 Load Config to bring it back." if backup else "")
        )

    def _on_pause_changed(self, paused: bool):
        """Called from the hook thread when the pause hotkey is used"""
        self.post_to_ui(lambda: self._update_status(self.remapper.running))

    def _refresh_lists(self):
        """Refresh the mapping, blocked key and Copilot views"""
        self._refresh_mappings()
        self._refresh_blocked()
        if hasattr(self, 'copilot_mode_menu'):
            self._refresh_copilot()
    
    def _refresh_mappings(self):
        """Refresh the mappings list"""
        # Clear existing widgets
        for widget in self.mapping_widgets:
            widget.destroy()
        self.mapping_widgets.clear()
        self.selected_mapping = None
        
        # Add mappings
        mappings = self.remapper.list_mappings()
        for i, m in enumerate(mappings):
            row = ctk.CTkFrame(self.mappings_frame, fg_color="#363636" if i % 2 == 0 else "#2b2b2b", corner_radius=5)
            row.pack(fill="x", pady=2)
            row.mapping = m
            row.mapping_source = m['source']

            # Status indicator
            # A text rule is also inert while typing is switched off in Settings
            paused_by_switch = (m['action'] == "text"
                                and not self.remapper.settings.type_text_enabled)
            status_color = "#27ae60" if m['enabled'] and not paused_by_switch else "#7f8c8d"
            status = ctk.CTkLabel(row, text="●", width=30, text_color=status_color)
            status.pack(side="left", padx=5)

            # Source
            ctk.CTkLabel(row, text=m['source'], width=110).pack(side="left", padx=5)

            # Arrow
            ctk.CTkLabel(row, text="→", width=20).pack(side="left")

            # Target - the keys it sends, the text it types, or what it opens
            ctk.CTkLabel(
                row, text=m['display_target'] + ("  (off)" if paused_by_switch else ""),
                width=110, anchor="w",
                text_color="#7f8c8d" if paused_by_switch else None
            ).pack(side="left", padx=5)

            # Hold role
            ctk.CTkLabel(row, text=m['hold'] or "-", width=70,
                         text_color="gray" if not m['hold'] else None).pack(side="left", padx=5)

            # App scope
            ctk.CTkLabel(row, text=m['app'] or "all", width=90,
                         text_color="gray" if not m['app'] else "#5dade2").pack(side="left", padx=5)

            # Description
            ctk.CTkLabel(row, text=m['description'] or "-", anchor="w").pack(side="left", padx=10, fill="x", expand=True)

            # Make row clickable
            row.bind("<Button-1>", lambda e, r=row: self._select_mapping(r))
            row.bind("<Double-Button-1>", lambda e, r=row: self._edit_mapping(r))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, r=row: self._select_mapping(r))
                child.bind("<Double-Button-1>", lambda e, r=row: self._edit_mapping(r))

            self.mapping_widgets.append(row)

        # Rows were added/removed, so the scrollbar may no longer be needed
        self.after(60, self.mappings_frame._refresh_scrollbar)
    
    def _refresh_blocked(self):
        """Refresh the blocked keys list"""
        # Clear existing widgets
        for widget in self.blocked_widgets:
            widget.destroy()
        self.blocked_widgets.clear()
        self.selected_blocked = None
        
        # Add blocked keys
        blocked = self.remapper.list_blocked_keys()
        for i, b in enumerate(blocked):
            row = ctk.CTkFrame(self.blocked_frame, fg_color="#363636" if i % 2 == 0 else "#2b2b2b", corner_radius=5)
            row.pack(fill="x", pady=2)
            row.blocked_key = b['key']
            row.blocked_app = b['app']

            # Status indicator
            status_color = "#e74c3c" if b['enabled'] else "#7f8c8d"
            status = ctk.CTkLabel(row, text="🚫" if b['enabled'] else "○", width=30, text_color=status_color)
            status.pack(side="left", padx=5)

            # Key
            ctk.CTkLabel(row, text=b['key'], width=150).pack(side="left", padx=5)

            # App scope
            ctk.CTkLabel(row, text=b['app'] or "all", width=90,
                         text_color="gray" if not b['app'] else "#5dade2").pack(side="left", padx=5)

            # Description
            ctk.CTkLabel(row, text=b['description'] or "-", anchor="w").pack(side="left", padx=10, fill="x", expand=True)
            
            # Make row clickable
            row.bind("<Button-1>", lambda e, r=row: self._select_blocked(r))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, r=row: self._select_blocked(r))
            
            self.blocked_widgets.append(row)

        self.after(60, self.blocked_frame._refresh_scrollbar)
    
    def _select_mapping(self, row):
        """Select a mapping row"""
        # Deselect previous
        if self.selected_mapping:
            idx = self.mapping_widgets.index(self.selected_mapping) if self.selected_mapping in self.mapping_widgets else 0
            self.selected_mapping.configure(fg_color="#363636" if idx % 2 == 0 else "#2b2b2b")
        
        # Select new
        self.selected_mapping = row
        row.configure(fg_color="#1a5276")
    
    def _select_blocked(self, row):
        """Select a blocked key row"""
        # Deselect previous
        if self.selected_blocked:
            idx = self.blocked_widgets.index(self.selected_blocked) if self.selected_blocked in self.blocked_widgets else 0
            self.selected_blocked.configure(fg_color="#363636" if idx % 2 == 0 else "#2b2b2b")
        
        # Select new
        self.selected_blocked = row
        row.configure(fg_color="#1a5276")
    
    def _add_mapping(self):
        """Open dialog to add a mapping"""
        dialog = AddMappingDialog(self, self.remapper)
        self.wait_window(dialog)
        if dialog.result:
            self._refresh_mappings()
            self.remapper.save_config()
    
    def _edit_mapping(self, row=None):
        """Edit the selected (or double-clicked) mapping"""
        row = row or self.selected_mapping
        if not row:
            messagebox.showwarning("Warning", "Please select a mapping to edit.")
            return

        self._select_mapping(row)
        dialog = AddMappingDialog(self, self.remapper, existing=row.mapping)
        self.wait_window(dialog)
        if dialog.result:
            self._refresh_mappings()
            self.remapper.save_config()

    def _remove_mapping(self):
        """Remove selected mapping"""
        if not self.selected_mapping:
            messagebox.showwarning("Warning", "Please select a mapping to remove.")
            return

        mapping = self.selected_mapping.mapping
        source, app = mapping['source'], mapping['app']
        scope = f" in {app}" if app else ""
        if messagebox.askyesno("Confirm", f"Remove mapping for '{source}'{scope}?"):
            self.remapper.remove_mapping(source, app)
            self._refresh_mappings()
            self.remapper.save_config()

    def _toggle_mapping(self):
        """Toggle selected mapping"""
        if not self.selected_mapping:
            messagebox.showwarning("Warning", "Please select a mapping to toggle.")
            return

        mapping = self.selected_mapping.mapping
        self.remapper.toggle_mapping(mapping['source'], mapping['app'])
        self._refresh_mappings()
        self.remapper.save_config()
    
    def _block_key(self):
        """Open dialog to block a key"""
        dialog = BlockKeyDialog(self, self.remapper)
        self.wait_window(dialog)
        if dialog.result:
            self._refresh_blocked()
            self.remapper.save_config()
    
    def _unblock_key(self):
        """Unblock selected key"""
        if not self.selected_blocked:
            messagebox.showwarning("Warning", "Please select a key to unblock.")
            return
        
        key = self.selected_blocked.blocked_key
        app = self.selected_blocked.blocked_app
        scope = f" in {app}" if app else ""
        if messagebox.askyesno("Confirm", f"Unblock key '{key}'{scope}?"):
            self.remapper.unblock_key(key, app)
            self._refresh_blocked()
            self.remapper.save_config()
    
    def _toggle_blocked(self):
        """Toggle selected blocked key"""
        if not self.selected_blocked:
            messagebox.showwarning("Warning", "Please select a blocked key to toggle.")
            return
        
        self.remapper.toggle_blocked_key(
            self.selected_blocked.blocked_key, self.selected_blocked.blocked_app
        )
        self._refresh_blocked()
        self.remapper.save_config()
    
    def _start_remapper(self):
        """Start the remapper"""
        if not self.remapper.has_work():
            messagebox.showwarning(
                "Nothing to do yet",
                "Add a mapping or a blocked key, set up the Copilot key, or turn on a "
                "Gaming option in Settings first."
            )
            return
        
        if self.remapper.start():
            self._update_status(True)
            messagebox.showinfo("Started", "Key remapper is now active!\n\nYour mappings and blocked keys are working.")
        else:
            messagebox.showerror(
                "Error",
                "Failed to install the keyboard hook.\n\n"
                f"See {CONFIG_DIR / 'key_remapper.log'} for details."
            )
    
    def _stop_remapper(self):
        """Stop the remapper"""
        self.remapper.stop()
        self._update_status(False)
    
    def _update_status(self, running: bool):
        """Update the status indicator"""
        if running and self.remapper.paused:
            self.status_indicator.configure(text_color="#f39c12")
            self.status_label.configure(text="PAUSED")
            self.start_btn.configure(state="disabled", fg_color=START_IDLE)
            self.stop_btn.configure(state="normal", fg_color=STOP_COLOR)
        elif running:
            self.status_indicator.configure(text_color="#27ae60")
            self.status_label.configure(text="ACTIVE")
            self.start_btn.configure(state="disabled", fg_color=START_IDLE)
            self.stop_btn.configure(state="normal", fg_color=STOP_COLOR)
        else:
            self.status_indicator.configure(text_color="#e74c3c")
            self.status_label.configure(text="STOPPED")
            self.start_btn.configure(state="normal", fg_color=START_COLOR)
            self.stop_btn.configure(state="disabled", fg_color=STOP_IDLE)

        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.icon = self._create_tray_icon()
            except Exception:
                pass
    
    def _save_config(self):
        """Save a copy of the setup somewhere of the user's choosing."""
        filepath = filedialog.asksaveasfilename(
            title="Save a copy of your setup",
            initialdir=_backup_folder(),
            initialfile=time.strftime("Key Remapper backup %Y-%m-%d.json"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filepath:
            filepath = Path(filepath)
            # Saving onto the live file makes a "backup" that Reset - and every
            # change - overwrites. It is exactly how a setup gets lost.
            if _same_file(filepath, CONFIG_FILE):
                messagebox.showwarning(
                    "That isn't a backup",
                    "That is the file Key Remapper already saves to automatically. "
                    "Every change, and Reset, overwrites it - so a copy there would "
                    "not protect anything.\n\n"
                    "Choose another folder or name, such as your Documents folder."
                )
                return
            if self.remapper.save_config(filepath):
                self.config_label.configure(text=f"Config: {filepath.name}")
                messagebox.showinfo("Saved", f"Configuration saved to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to save configuration.")
    
    def _load_config(self):
        """Replace the current setup with a saved copy."""
        filepath = filedialog.askopenfilename(
            title="Load a saved setup",
            initialdir=_backup_folder(),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        filepath = Path(filepath)

        # Loading replaces every rule, so keep what is there now - unless the
        # file chosen *is* the live setup, which would be a pointless copy
        backup = None
        if not _same_file(filepath, CONFIG_FILE):
            backup = self.remapper.backup_config("load")

        if not self.remapper.load_config(filepath):
            messagebox.showerror(
                "Couldn't load that file",
                f"{filepath.name} isn't a Key Remapper setup, or it is damaged.\n\n"
                "Nothing was changed."
            )
            return

        # Make it the live setup, so it is still there after a restart
        self.remapper.save_config()
        self._refresh_lists()
        self._refresh_settings_widgets()
        self.config_label.configure(text=f"Config: {filepath.name}")
        messagebox.showinfo(
            "Loaded",
            f"Loaded {len(self.remapper.mappings)} mapping(s) and "
            f"{len(self.remapper.blocked_keys)} blocked key(s) from:\n{filepath}"
            + (f"\n\nYour previous setup was backed up to:\n{backup}" if backup else "")
        )
    
    def _show_available_keys(self):
        """Open the key reference (or bring the open one forward)."""
        window = getattr(self, '_keys_window', None)
        if window is not None and window.winfo_exists():
            window.lift()
            window.focus_force()
            return
        self._keys_window = KeyReferenceWindow(self)

    def _show_about(self):
        """Show About dialog with usage instructions and credits"""
        about_window = ctk.CTkToplevel(self)
        about_window.title("About Key Remapper")
        about_window.geometry("560x600")
        about_window.resizable(False, False)
        about_window.transient(self)
        about_window.grab_set()

        # Center the window
        about_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 560) // 2
        y = self.winfo_y() + (self.winfo_height() - 600) // 2
        about_window.geometry(f"+{x}+{y}")

        # Title
        ctk.CTkLabel(
            about_window,
            text="Key Remapper",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            about_window,
            text=f"Gaming Edition - Version {__version__}",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(pady=(0, 15))

        # Scrollable content
        content_frame = AutoHideScrollableFrame(about_window, width=510, height=340)
        content_frame.pack(padx=20, pady=10, fill="both", expand=True)

        about_text = """WHAT THIS APP DOES
═══════════════════════════════════════

Key Remapper rewrites your keyboard at the lowest level
Windows allows, so it keeps working in games and apps
that ignore ordinary remapping tools.

A key can:
  • Become any other key or combination
  • Type text that ignores your keyboard layout
  • Launch a program, app, file or website
  • Send volume, media and browser keys
  • Do nothing at all, so it cannot misfire
  • Do one thing tapped and another held
  • Behave differently inside one application

GETTING STARTED
───────────────
  1. "Key Mappings" tab → "+ Add Mapping"
  2. Click 🎯 Detect and press the key you want to
     change, or click ⌨ to pick it from the list
  3. Choose what it should do: send keys, type text,
     launch an app, or open a website
  4. Click "Add" — the rule is saved immediately
  5. Click "▶ Start" at the top to make it live

The status light shows where you are:
  🔴 STOPPED  nothing is intercepted
  🟢 ACTIVE   your rules are running
  🟠 PAUSED   rules suspended, hook still installed

THE FOUR TABS
─────────────
  Key Mappings  turn keys into other keys or actions
  Blocked Keys  disable keys outright
  Copilot Key   repurpose the dedicated Copilot key
  Settings      pause hotkey, startup, typing, gaming,
                reset

KEY MAPPINGS
────────────
Examples:
  • CapsLock → Escape (a favourite among Vim users)
  • F1 → Ctrl+S (quick save)
  • F9 → Mute, F10/F11 → Volume down/up
  • Mouse4 → Ctrl+C (side button copies)
Double-click any row later to edit it, or select it
and use "Remove Selected" / "Toggle On/Off".

LAUNCH AN APP FROM A KEY
──────────────────────
"What should it do?" offers four things:
  • Send other key(s) — the classic remap, with a
    picker for volume, media, function and browser keys
  • Type text — see below
  • Launch a program or app — pick Calculator,
    Explorer, Terminal and friends, browse for an .exe,
    or paste shell:AppsFolder\\… for a Store app
  • Open a website — any URL, in your default browser
▶ Test runs it once without pressing the key, so you
can check a path before you commit to it.

TYPE TEXT (LAYOUT-INDEPENDENT)
──────────────────────────────
"Send other key(s)" sends a key POSITION, and Windows
turns it into a character using your current layout.
Map a key to "period" and it types "." in English but
"ю" in Russian - the remap follows the layout.

"Type text" sends the characters themselves, so they
come out the same in every layout:
  • rctrl → "."   and   shift+rctrl → ","
    a dedicated period/comma key in any layout
  • ctrl+alt+m → your email address
Shift does not change typed text, so give a shifted
character its own rule, as above. Holding the key
repeats the text, like any other key.

Two limits: games that read raw keyboard input do not
see typed text (it is for typing, not gaming), and the
characters go wherever the keyboard focus is.

Settings → "Typing text" pauses every text rule at
once without deleting them; paused rules show "(off)".

BLOCKED KEYS
────────────
Completely disable keys to prevent accidental presses:
  • Block "/" to stop chat opening mid-game
  • Block "win" so you never minimise a fullscreen game
  • Block "escape" to avoid the pause menu

COPILOT KEY
───────────
The Copilot key is not a real key — the keyboard
firmware sends SHIFT+WIN+F23 on most laptops. That is
why blocking F23 alone does nothing, and why releasing
the key can pop the Start menu.

The "Copilot Key" tab lets you:
  • 🎯 Detect exactly what your keyboard sends
  • Give back the key it replaced: Right Alt, Windows,
    Menu or Right Ctrl — one click each
  • Disable it, send other keys, or launch something

NUMPAD + SHIFT IN GAMES
───────────────────────
With NumLock on, Windows turns Shift+Numpad into arrow
keys - and to do it, it briefly lets go of Shift. In a
game that means a numpad binding misfires and a held
Shift (sprint, crouch) drops for an instant.

Settings → Gaming → "Keep numpad keys as numbers while
Shift is held" stops both. Off by default: outside games,
Shift+Numpad selecting text is what people expect. Real
arrow keys, and the numpad with NumLock off, are never
touched.

⚠ Most games run as administrator, so Key Remapper has
to be run as administrator too (right-click → Run as
administrator). Some games and anti-cheat systems block
keyboard hooks entirely, and there this cannot work.

PER-APP PROFILES
────────────────
Leave "Only in this app" empty for a global rule, or
type an executable (game.exe) to scope it. App rules
beat global ones for the same key.

DUAL-ROLE KEYS (TAP vs HOLD)
────────────────────────────
Fill in "When held instead" to give a key two jobs:
  • CapsLock → Escape when tapped, Ctrl when held
The threshold lives in the Settings tab.

PAUSE HOTKEY
────────────
Settings tab → set a hotkey (e.g. ctrl+alt+f12) to
suspend every mapping without stopping the remapper.
Anything held down is released, never left stuck.

KEY DETECTION
─────────────
Click 🎯 Detect, then press the keys you want. Every
keystroke is intercepted until you do, so Windows-key
and Copilot combinations are captured correctly. The
dialog also shows the raw code your keyboard sent, and
writes vk0x5D for keys that have no friendly name.

Not sure what a key is called? Click ⌨ beside any key
field: every key is listed by category, and clicking
keys builds the entry for you - ctrl, then s, gives
ctrl+s. "📋 Show Keys" opens the same list on its own;
there, clicking a key copies its name.

⚠ THE Fn KEY — PLEASE READ
───────────────────────
On the overwhelming majority of keyboards, Fn never
reaches Windows at all. It is handled inside the
keyboard controller, which simply sends a different
key for the combination. No application can see a key
the hardware never sends, so:

  • Fn cannot be used as a modifier like Ctrl or Shift
  • 🎯 Detect cannot record "Fn" on its own
  • Fn key mapping is therefore very limited

What does work: press the WHOLE combination during
🎯 Detect. Hold Fn and tap F12, and whatever your
keyboard truly sends is recorded — often a media key
such as VOLUMEUP, sometimes plain F12, sometimes a raw
code like vk0x97. Map that, and it behaves exactly as
you wanted. If Fn+F12 records as plain "F12", then your
keyboard is sending the two presses identically and
they cannot be told apart.

SYSTEM TRAY
───────────
Closing the window keeps the remapper running in the
system tray. Windows 11 hides new tray icons behind
the "^" arrow on the taskbar — drag the K icon out to
keep it in view. Click the icon to reopen this window,
or right-click it for Pause / Resume and Exit.

Starting the app again while it is hidden reopens the
window instead of launching a second copy.

SUPPORTED KEYS
──────────────
  • Letters: a-z          • Numbers: 0-9
  • Function keys: f1-f24 (including F13-F24)
  • Modifiers: ctrl, shift, alt, win
  • Special: escape, tab, space, enter, apps, etc.
  • Media: playpause, mute, volumeup, calculator, ...
  • Mouse: mouse3, mouse4, mouse5 (as a source)
  • Raw codes: vk0x5D, for keys with no name
  • Combinations: ctrl+a, win+shift+f23, etc.
See "📋 Show Keys" for the full list.

SAVING, LOADING AND STARTING OVER
────────────────────────────────
Changes save themselves automatically. "💾 Save Config"
is for keeping a COPY - it suggests your Documents
folder, and won't save over the automatic file, because
a copy there wouldn't protect anything.

"📂 Load Config" replaces your current setup with a saved
copy and keeps it after a restart.

Settings → "Reset everything to defaults" clears every
rule and setting.

Reset and Load both save a backup of your current setup
first, so neither can lose it. The last 10 backups are
kept in the "backups" folder next to your settings - use
Load Config to bring one back.

IMPORTANT NOTES
───────────────
  • Changes are saved automatically
  • Click "▶ Start" to activate your mappings
  • Runs fine as a normal user. Administrator rights
    are only needed to affect windows that themselves
    run elevated (some games, Task Manager, etc.)
  • Your keystrokes are never recorded anywhere

═══════════════════════════════════════

Built by Li Fan, 2026
Source, releases and issues:
{project_url}

If this app saved you some frustration, you are very
welcome to buy me a coffee - the button is below.
""".replace("{project_url}", PROJECT_URL)

        text_label = ctk.CTkLabel(
            content_frame,
            text=about_text,
            font=ctk.CTkFont(family="Consolas", size=12),
            justify="left",
            anchor="w"
        )
        text_label.pack(padx=10, pady=5, anchor="w")

        # Environment info (diagnostics, not a warning)
        ctk.CTkLabel(
            about_window,
            text=f"Settings folder: {CONFIG_DIR}    •    "
                 f"Elevated: {'yes' if check_admin() else 'no (fine for most apps)'}",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=(2, 8))

        # Credits, project link and donation
        btn_frame = ctk.CTkFrame(about_window, fg_color="transparent")
        btn_frame.pack(pady=(0, 15))

        ctk.CTkButton(
            btn_frame,
            text="🐙 GitHub",
            command=lambda: webbrowser.open(PROJECT_URL),
            width=120,
            fg_color="#4a4a4a",
            hover_color=GRAY_BUTTON_HOVER
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame,
            text="💛 Donate",
            command=lambda: webbrowser.open(DONATE_URL),
            width=120,
            fg_color="#f0a500",
            hover_color="#ffc233",
            text_color="#1a1a1a"
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame,
            text="Close",
            command=about_window.destroy,
            width=100
        ).pack(side="left", padx=6)

    
    def _on_close(self):
        """Handle window close"""
        # Every prompt here has a Cancel: a plain Yes/No box makes Windows grey
        # out the title bar's X, leaving no way to back out of closing. With a
        # Cancel button, X and Esc both work and both mean "never mind".
        if TRAY_AVAILABLE and self.remapper.running:
            choice = messagebox.askyesnocancel(
                "Keep running in the tray?",
                "Key Remapper is running.\n\n"
                "Yes \u2014 keep it running in the system tray\n"
                "No \u2014 stop it and quit\n"
                "Cancel \u2014 go back to the window"
            )
            if choice is None:
                return
            if choice:
                self._minimize_to_tray()
                return
            self.remapper.stop()
        elif self.remapper.running:
            if not messagebox.askokcancel(
                "Stop and quit?",
                "Key Remapper is running. Closing the window stops it.\n\n"
                "OK \u2014 stop it and quit\n"
                "Cancel \u2014 go back to the window"
            ):
                return
            self.remapper.stop()
        
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
    
    def _create_tray_icon(self):
        """Create a system tray icon image"""
        # Green when active, amber when paused, red when stopped
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        if not self.remapper.running:
            color = (231, 76, 60)
        elif self.remapper.paused:
            color = (243, 156, 18)
        else:
            color = (39, 174, 96)
        draw.ellipse([4, 4, size-4, size-4], fill=color)
        
        # Draw "K" in the center
        draw.text((size//2 - 8, size//2 - 12), "K", fill="white")
        
        return image
    
    def _minimize_to_tray(self):
        """Minimize the application to system tray"""
        if not TRAY_AVAILABLE:
            self.iconify()
            return

        if self.tray_icon:
            self.withdraw()
            return

        def on_show(icon, item):
            icon.stop()
            self.after(0, self._restore_from_tray)

        def on_toggle(icon, item):
            if self.remapper.running:
                self.remapper.stop()
            else:
                self.remapper.start()
            # Update icon
            icon.icon = self._create_tray_icon()

        def on_pause(icon, item):
            if self.remapper.running:
                self.remapper.set_paused(not self.remapper.paused)
                icon.icon = self._create_tray_icon()

        def on_exit(icon, item):
            icon.stop()
            self.tray_icon = None
            self.remapper.stop()
            self.after(0, self.destroy)

        # Create tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", on_show, default=True),
            pystray.MenuItem(
                "Toggle Remapper",
                on_toggle
            ),
            pystray.MenuItem("Pause / Resume", on_pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit)
        )
        
        # Create and run tray icon
        self.tray_icon = pystray.Icon(
            "key_remapper",
            self._create_tray_icon(),
            "Key Remapper - " + ("Active" if self.remapper.running else "Stopped"),
            menu
        )
        
        # Hide window and run tray icon
        self.withdraw()
        
        def on_ready(icon):
            # Runs once the icon actually exists, which notify() requires
            icon.visible = True
            if self._tray_announced:
                return
            self._tray_announced = True
            try:
                icon.notify(
                    "Key Remapper is still running, hidden here in the system tray.\n"
                    "Click this icon to reopen the window.",
                    "Key Remapper"
                )
            except Exception:
                # Notifications can be turned off system-wide; never fail over it
                logger.debug("Could not show the tray notification", exc_info=True)

        # Run tray icon in a separate thread
        tray_thread = threading.Thread(
            target=lambda: self.tray_icon.run(setup=on_ready), daemon=True
        )
        tray_thread.start()

    def bring_to_front(self):
        """Show the window again - called when a second copy of the app starts."""
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                logger.debug("Could not stop the tray icon", exc_info=True)
        self._restore_from_tray()
    
    def _restore_from_tray(self):
        """Restore window from system tray"""
        self.tray_icon = None
        self.deiconify()
        self.lift()
        self.focus_force()
        self._update_status(self.remapper.running)


def main():
    """Main entry point"""
    start_minimized = "--minimized" in sys.argv

    # A second copy would install its own keyboard hook on top of the first.
    # Hand over to the instance that is already running instead.
    instance = SingleInstance()
    if not instance.acquire():
        instance.signal_existing()
        return

    app = KeyRemapperGUI(start_minimized=start_minimized)
    instance.listen(lambda: app.post_to_ui(app.bring_to_front))
    try:
        app.mainloop()
    finally:
        instance.release()


if __name__ == "__main__":
    main()
