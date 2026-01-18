"""
Windows Key Remapper - Modern GUI Edition
==========================================
A modern GUI wrapper for the key remapper using customtkinter.
Supports system tray operation for gaming.

Requirements:
- Windows 11 (also works on Windows 10)
- Python 3.8+
- Run as Administrator for full functionality
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
import json
from pathlib import Path
from typing import Optional
import sys
import os

# Import the core remapper functionality
from key_remapper import (
    KeyRemapper, CONFIG_FILE, KEY_NAME_TO_VK, 
    check_admin
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


class KeyCaptureDialog(ctk.CTkToplevel):
    """Dialog to capture a key press"""
    
    def __init__(self, parent, title: str = "Press a Key"):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.detected_keys = []
        
        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 280) // 2
        self.geometry(f"+{x}+{y}")
        
        # UI
        self.label = ctk.CTkLabel(
            self, 
            text="Press any key or key combination...",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.label.pack(pady=(20, 10))
        
        self.detected_label = ctk.CTkLabel(
            self,
            text="Detected: (none)",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.detected_label.pack(pady=5)
        
        self.info_label = ctk.CTkLabel(
            self,
            text="Hold modifiers (Ctrl/Shift/Alt) then press a key\nNote: Win key combos may not detect - type manually below",
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
        btn_frame.pack(pady=15)
        
        self.use_btn = ctk.CTkButton(btn_frame, text="Use This Key", command=self._use_key, width=120, state="disabled")
        self.use_btn.pack(side="left", padx=5)
        
        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100)
        self.cancel_btn.pack(side="left", padx=5)
        
        # Bind key events
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self.focus_force()
    
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
            detected_str = "+".join(keys)
            self.detected_label.configure(text=f"Detected: {detected_str}", text_color="#27ae60")
            self.use_btn.configure(state="normal")
    
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


class AddMappingDialog(ctk.CTkToplevel):
    """Dialog to add a new key mapping"""
    
    def __init__(self, parent, remapper: KeyRemapper):
        super().__init__(parent)
        self.title("Add Key Mapping")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.remapper = remapper
        self.result = None
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
        self.geometry(f"+{x}+{y}")
        
        # Source key
        ctk.CTkLabel(self, text="Source Key (key to remap):", font=ctk.CTkFont(size=13)).pack(pady=(20, 5))
        source_frame = ctk.CTkFrame(self, fg_color="transparent")
        source_frame.pack(pady=5)
        self.source_entry = ctk.CTkEntry(source_frame, width=240, placeholder_text="e.g., capslock, ctrl+a, f1")
        self.source_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(source_frame, text="🎯 Detect", command=self._detect_source, width=60).pack(side="left")
        
        # Target key
        ctk.CTkLabel(self, text="Target Key (what it becomes):", font=ctk.CTkFont(size=13)).pack(pady=(15, 5))
        target_frame = ctk.CTkFrame(self, fg_color="transparent")
        target_frame.pack(pady=5)
        self.target_entry = ctk.CTkEntry(target_frame, width=240, placeholder_text="e.g., escape, ctrl+c, shift+f1")
        self.target_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(target_frame, text="🎯 Detect", command=self._detect_target, width=60).pack(side="left")
        
        # Description
        ctk.CTkLabel(self, text="Description (optional):", font=ctk.CTkFont(size=13)).pack(pady=(15, 5))
        self.desc_entry = ctk.CTkEntry(self, width=300, placeholder_text="e.g., Caps Lock to Escape")
        self.desc_entry.pack(pady=5)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="Add", command=self._on_add, width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100).pack(side="left", padx=10)
        
        self.source_entry.focus()
    
    def _detect_source(self):
        """Open key detection dialog for source key"""
        dialog = KeyCaptureDialog(self, "Detect Source Key")
        self.wait_window(dialog)
        if dialog.result:
            self.source_entry.delete(0, 'end')
            self.source_entry.insert(0, dialog.result)
    
    def _detect_target(self):
        """Open key detection dialog for target key"""
        dialog = KeyCaptureDialog(self, "Detect Target Key")
        self.wait_window(dialog)
        if dialog.result:
            self.target_entry.delete(0, 'end')
            self.target_entry.insert(0, dialog.result)
    
    def _on_add(self):
        source = self.source_entry.get().strip()
        target = self.target_entry.get().strip()
        desc = self.desc_entry.get().strip()
        
        if not source or not target:
            messagebox.showerror("Error", "Please enter both source and target keys.")
            return
        
        if self.remapper.add_mapping(source, target, desc):
            self.result = (source, target, desc)
            messagebox.showinfo(
                "Mapping Added",
                f"Key mapping created successfully!\n\n"
                f"Source: {source}\n"
                f"Target: {target}\n"
                f"{('Description: ' + desc) if desc else ''}"
            )
            self.destroy()
        else:
            messagebox.showerror("Error", f"Invalid key name. Check spelling.\nAvailable keys include: a-z, 0-9, f1-f12, ctrl, shift, alt, escape, space, etc.")


class BlockKeyDialog(ctk.CTkToplevel):
    """Dialog to block a key"""
    
    def __init__(self, parent, remapper: KeyRemapper):
        super().__init__(parent)
        self.title("Block Key")
        self.geometry("400x280")
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
        self.key_entry = ctk.CTkEntry(key_frame, width=240, placeholder_text="e.g., /, win, alt+tab, f1")
        self.key_entry.pack(side="left", padx=(0, 5))
        ctk.CTkButton(key_frame, text="🎯 Detect", command=self._detect_key, width=60).pack(side="left")
        
        # Description
        ctk.CTkLabel(self, text="Description (optional):", font=ctk.CTkFont(size=13)).pack(pady=(10, 5))
        self.desc_entry = ctk.CTkEntry(self, width=300, placeholder_text="e.g., Block chat key in games")
        self.desc_entry.pack(pady=5)
        
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
        
        if not key:
            messagebox.showerror("Error", "Please enter a key to block.")
            return
        
        if self.remapper.block_key(key, desc):
            self.result = (key, desc)
            self.destroy()
        else:
            messagebox.showerror("Error", f"Invalid key name: '{key}'")


class KeyRemapperGUI(ctk.CTk):
    """Main GUI Application"""
    
    def __init__(self):
        super().__init__()
        
        self.title("Key Remapper - Gaming Edition")
        self.geometry("700x600")
        self.minsize(600, 500)
        
        # Initialize remapper
        self.remapper = KeyRemapper()
        self.remapper.load_config()
        
        # Build UI
        self._create_ui()
        self._refresh_lists()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
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
            fg_color="#27ae60",
            hover_color="#2ecc71"
        )
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame, 
            text="■ Stop", 
            command=self._stop_remapper,
            width=100,
            fg_color="#c0392b",
            hover_color="#e74c3c",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        # Tabview for mappings and blocked keys
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.tab_mappings = self.tabview.add("Key Mappings")
        self.tab_blocked = self.tabview.add("Blocked Keys")
        
        # === Mappings Tab ===
        self._create_mappings_tab()
        
        # === Blocked Keys Tab ===
        self._create_blocked_tab()
        
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
            text="Remove Selected", 
            command=self._remove_mapping,
            width=130,
            fg_color="#7f8c8d",
            hover_color="#95a5a6"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, 
            text="Toggle On/Off", 
            command=self._toggle_mapping,
            width=130,
            fg_color="#7f8c8d",
            hover_color="#95a5a6"
        ).pack(side="left", padx=5)
        
        # Scrollable frame for mappings
        self.mappings_frame = ctk.CTkScrollableFrame(self.tab_mappings)
        self.mappings_frame.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(self.mappings_frame, fg_color="#2b2b2b", corner_radius=5)
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header, text="", width=30).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Source", width=120, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="→", width=30).pack(side="left")
        ctk.CTkLabel(header, text="Target", width=120, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
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
            fg_color="#7f8c8d",
            hover_color="#95a5a6"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, 
            text="Toggle On/Off", 
            command=self._toggle_blocked,
            width=130,
            fg_color="#7f8c8d",
            hover_color="#95a5a6"
        ).pack(side="left", padx=5)
        
        # Scrollable frame for blocked keys
        self.blocked_frame = ctk.CTkScrollableFrame(self.tab_blocked)
        self.blocked_frame.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(self.blocked_frame, fg_color="#2b2b2b", corner_radius=5)
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header, text="", width=30).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Key", width=150, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Description", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        
        self.blocked_widgets = []
        self.selected_blocked = None
    
    def _refresh_lists(self):
        """Refresh both mapping and blocked key lists"""
        self._refresh_mappings()
        self._refresh_blocked()
    
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
            row.mapping_source = m['source']
            
            # Status indicator
            status_color = "#27ae60" if m['enabled'] else "#7f8c8d"
            status = ctk.CTkLabel(row, text="●", width=30, text_color=status_color)
            status.pack(side="left", padx=5)
            
            # Source
            ctk.CTkLabel(row, text=m['source'], width=120).pack(side="left", padx=5)
            
            # Arrow
            ctk.CTkLabel(row, text="→", width=30).pack(side="left")
            
            # Target
            ctk.CTkLabel(row, text=m['target'], width=120).pack(side="left", padx=5)
            
            # Description
            ctk.CTkLabel(row, text=m['description'] or "-", anchor="w").pack(side="left", padx=10, fill="x", expand=True)
            
            # Make row clickable
            row.bind("<Button-1>", lambda e, r=row: self._select_mapping(r))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, r=row: self._select_mapping(r))
            
            self.mapping_widgets.append(row)
    
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
            
            # Status indicator
            status_color = "#e74c3c" if b['enabled'] else "#7f8c8d"
            status = ctk.CTkLabel(row, text="🚫" if b['enabled'] else "○", width=30, text_color=status_color)
            status.pack(side="left", padx=5)
            
            # Key
            ctk.CTkLabel(row, text=b['key'], width=150).pack(side="left", padx=5)
            
            # Description
            ctk.CTkLabel(row, text=b['description'] or "-", anchor="w").pack(side="left", padx=10, fill="x", expand=True)
            
            # Make row clickable
            row.bind("<Button-1>", lambda e, r=row: self._select_blocked(r))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, r=row: self._select_blocked(r))
            
            self.blocked_widgets.append(row)
    
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
    
    def _remove_mapping(self):
        """Remove selected mapping"""
        if not self.selected_mapping:
            messagebox.showwarning("Warning", "Please select a mapping to remove.")
            return
        
        source = self.selected_mapping.mapping_source
        if messagebox.askyesno("Confirm", f"Remove mapping for '{source}'?"):
            self.remapper.remove_mapping(source)
            self._refresh_mappings()
            self.remapper.save_config()
    
    def _toggle_mapping(self):
        """Toggle selected mapping"""
        if not self.selected_mapping:
            messagebox.showwarning("Warning", "Please select a mapping to toggle.")
            return
        
        source = self.selected_mapping.mapping_source
        self.remapper.toggle_mapping(source)
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
        if messagebox.askyesno("Confirm", f"Unblock key '{key}'?"):
            self.remapper.unblock_key(key)
            self._refresh_blocked()
            self.remapper.save_config()
    
    def _toggle_blocked(self):
        """Toggle selected blocked key"""
        if not self.selected_blocked:
            messagebox.showwarning("Warning", "Please select a blocked key to toggle.")
            return
        
        key = self.selected_blocked.blocked_key
        self.remapper.toggle_blocked_key(key)
        self._refresh_blocked()
        self.remapper.save_config()
    
    def _start_remapper(self):
        """Start the remapper"""
        if not self.remapper.mappings and not self.remapper.blocked_keys:
            messagebox.showwarning("Warning", "No mappings or blocked keys configured.")
            return
        
        if self.remapper.start():
            self._update_status(True)
            messagebox.showinfo("Started", "Key remapper is now active!\n\nYour mappings and blocked keys are working.")
        else:
            messagebox.showerror("Error", "Failed to start remapper.\nTry running as Administrator.")
    
    def _stop_remapper(self):
        """Stop the remapper"""
        self.remapper.stop()
        self._update_status(False)
    
    def _update_status(self, running: bool):
        """Update the status indicator"""
        if running:
            self.status_indicator.configure(text_color="#27ae60")
            self.status_label.configure(text="ACTIVE")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.status_indicator.configure(text_color="#e74c3c")
            self.status_label.configure(text="STOPPED")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
    
    def _save_config(self):
        """Save configuration with file dialog"""
        # Get default directory (user's Documents folder)
        default_dir = Path.home() / "Documents"
        
        filepath = filedialog.asksaveasfilename(
            title="Save Configuration",
            initialdir=default_dir,
            initialfile="key_remap_config.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            filepath = Path(filepath)
            if self.remapper.save_config(filepath):
                self.config_label.configure(text=f"Config: {filepath.name}")
                messagebox.showinfo("Saved", f"Configuration saved to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to save configuration.")
    
    def _load_config(self):
        """Load configuration with file dialog"""
        # Get default directory (user's Documents folder)
        default_dir = Path.home() / "Documents"
        
        filepath = filedialog.askopenfilename(
            title="Load Configuration",
            initialdir=default_dir,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            filepath = Path(filepath)
            if self.remapper.load_config(filepath):
                self._refresh_lists()
                self.config_label.configure(text=f"Config: {filepath.name}")
                messagebox.showinfo("Loaded", f"Configuration loaded from:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to load configuration.")
    
    def _show_available_keys(self):
        """Show available key names"""
        keys_window = ctk.CTkToplevel(self)
        keys_window.title("Available Key Names")
        keys_window.geometry("500x400")
        keys_window.transient(self)
        
        text = ctk.CTkTextbox(keys_window, font=ctk.CTkFont(family="Consolas", size=12))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        
        content = """AVAILABLE KEY NAMES
==================

LETTERS: a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z

NUMBERS: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9

FUNCTION KEYS: f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12
EXTENDED FUNCTION KEYS: f13, f14, f15, f16, f17, f18, f19, f20, f21, f22, f23, f24

NOTE: Windows Copilot key is typically win+shift+f23
      You can block this key combination to disable Copilot

MODIFIERS: ctrl, lctrl, rctrl, shift, lshift, rshift, alt, lalt, ralt, win, lwin, rwin

NAVIGATION: up, down, left, right, home, end, pageup, pagedown

SPECIAL KEYS: escape, esc, tab, capslock, caps, space, enter, return, backspace, delete, insert

NUMPAD: num0-num9, numplus, numminus, nummultiply, numdivide, numdecimal

PUNCTUATION: semicolon (;), comma (,), period (.), slash (/), backslash (\\), quote ('), grave (`), lbracket ([), rbracket (]), minus (-), equals (=)

COMBINATIONS:
Use + to combine keys, e.g.:
  ctrl+a
  shift+f1
  ctrl+shift+escape
  alt+tab
  win+shift+f23 (Copilot key)
"""
        text.insert("1.0", content)
        text.configure(state="disabled")
    
    def _show_about(self):
        """Show About dialog with usage instructions and credits"""
        about_window = ctk.CTkToplevel(self)
        about_window.title("About Key Remapper")
        about_window.geometry("550x520")
        about_window.resizable(False, False)
        about_window.transient(self)
        about_window.grab_set()
        
        # Center the window
        about_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 550) // 2
        y = self.winfo_y() + (self.winfo_height() - 520) // 2
        about_window.geometry(f"+{x}+{y}")
        
        # Title
        ctk.CTkLabel(
            about_window, 
            text="Key Remapper", 
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(pady=(20, 5))
        
        ctk.CTkLabel(
            about_window, 
            text="Gaming Edition - Version 2.0", 
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(pady=(0, 15))
        
        # Scrollable content
        content_frame = ctk.CTkScrollableFrame(about_window, width=500, height=350)
        content_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        about_text = """HOW TO USE THIS APPLICATION
═══════════════════════════════════════

Built by Li Fan, 2025
Created out of frustration at being unable to
disable or remap keys within a particular game.

NEW IN VERSION 2.0
──────────────────
✨ Extended function keys support (F13-F24)
✨ Interactive key detection with 🎯 Detect buttons
✨ Auto-save: Changes saved automatically
✨ Block Windows Copilot key (win+shift+f23)
✨ No admin warning on startup

KEY MAPPINGS (Remap Keys)
─────────────────────────
Remap any key to another key or key combination.

Examples:
  • CapsLock → Escape (great for Vim users)
  • F1 → Ctrl+S (quick save)
  • F23 → Disabled (block Copilot key)

To add a mapping:
  1. Click "Add Mapping"
  2. Click 🎯 Detect or type key name
  3. For Win key combos, type manually (e.g., win+shift+f23)
  4. Click "Add" - saves automatically!

BLOCKED KEYS (Disable Keys)
───────────────────────────
Completely disable keys to prevent accidental presses.

Examples:
  • Block "/" to prevent opening chat
  • Block "win+shift+f23" to disable Copilot
  • Block "Escape" to prevent pause menu

KEY DETECTION FEATURE
─────────────────────
Click 🎯 Detect buttons to capture key presses:
  • Press any key combination (Ctrl/Shift/Alt work)
  • For Win key combos, type manually in the field
  • Press Enter or click "Use This Key"

SUPPORTED KEYS
──────────────
• Letters: a-z
• Numbers: 0-9
• Function keys: f1-f24 (including extended F13-F24)
• Modifiers: ctrl, shift, alt, win
• Special: escape, tab, space, enter, etc.
• Combinations: ctrl+a, win+shift+f23, etc.

IMPORTANT NOTES
───────────────
• Changes are saved automatically
• Click "Start" to activate your mappings
• Works without admin (admin optional for some games)
• Close to system tray to keep running in background

═══════════════════════════════════════
"""
        
        text_label = ctk.CTkLabel(
            content_frame, 
            text=about_text,
            font=ctk.CTkFont(family="Consolas", size=12),
            justify="left",
            anchor="w"
        )
        text_label.pack(padx=10, pady=5, anchor="w")
        
        # Close button
        ctk.CTkButton(
            about_window, 
            text="Close", 
            command=about_window.destroy,
            width=100
        ).pack(pady=(0, 15))
    
    
    def _on_close(self):
        """Handle window close"""
        if TRAY_AVAILABLE and self.remapper.running:
            # Minimize to tray instead of closing
            if messagebox.askyesno(
                "Minimize to Tray?", 
                "Remapper is running. Minimize to system tray?\n\n"
                "Click 'No' to stop and exit completely."
            ):
                self._minimize_to_tray()
                return
            else:
                self.remapper.stop()
        elif self.remapper.running:
            if messagebox.askyesno("Confirm Exit", "Remapper is still running. Stop and exit?"):
                self.remapper.stop()
            else:
                return
        
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
    
    def _create_tray_icon(self):
        """Create a system tray icon image"""
        # Create a simple icon (green circle when active, red when stopped)
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw outer circle
        color = (39, 174, 96) if self.remapper.running else (231, 76, 60)
        draw.ellipse([4, 4, size-4, size-4], fill=color)
        
        # Draw "K" in the center
        draw.text((size//2 - 8, size//2 - 12), "K", fill="white")
        
        return image
    
    def _minimize_to_tray(self):
        """Minimize the application to system tray"""
        if not TRAY_AVAILABLE:
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
        
        def on_exit(icon, item):
            icon.stop()
            self.remapper.stop()
            self.after(0, self.destroy)
        
        # Create tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", on_show, default=True),
            pystray.MenuItem(
                "Toggle Remapper", 
                on_toggle
            ),
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
        
        # Run tray icon in a separate thread
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()
    
    def _restore_from_tray(self):
        """Restore window from system tray"""
        self.deiconify()
        self.lift()
        self.focus_force()
        self._update_status(self.remapper.running)


def main():
    """Main entry point"""
    app = KeyRemapperGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
