# Windows Key Remapper

A robust, gaming-compatible key remapping tool for Windows 11 (also works on Windows 10).

**Version 1.0** | Built by Li Fan, 2025

> *Created out of frustration at being unable to disable or remap keys within a particular game.*

## Features

- **Modern GUI**: Clean, dark-themed interface built with customtkinter
- **Gaming Compatible**: Uses low-level Windows hooks (`SetWindowsHookEx`) that work with most games and applications
- **Key Combinations**: Remap single keys to key combinations (e.g., `F1` → `Ctrl+S`, `F2` → `Ctrl+Shift+S`)
- **Key Blocking**: Completely disable specific keys to prevent accidental presses during gaming (e.g., block `/` key)
- **System Tray**: Minimize to system tray while remapper runs in the background
- **Standalone Executable**: Build a single `.exe` file - no Python installation required
- **Persistent Configuration**: Save and load your mappings to a JSON file
- **Toggle Mappings**: Enable/disable individual mappings or blocked keys without removing them
- **Logging**: All actions logged to `key_remapper.log` for troubleshooting

## Requirements

### For Running from Source
- Windows 10 or Windows 11
- Python 3.8 or higher
- **Administrator privileges** (required for gaming compatibility)

### For Executable
- Windows 10 or Windows 11
- **Administrator privileges**

## Installation

### Option 1: Run from Source

1. Clone or download this repository
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the GUI:
   ```powershell
   python key_remapper_gui.py
   ```

### Option 2: Build Standalone Executable

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. Run the build script:
   ```powershell
   python build.py
   ```
3. Find the executable at `dist/KeyRemapper.exe`
4. Right-click → Run as administrator

## Usage

### Running the GUI

**Important**: Run as Administrator for full gaming compatibility!

```powershell
# Right-click PowerShell -> Run as Administrator
python key_remapper_gui.py
```

### Menu Options

**Key Mappings:**
1. **Add mapping** - Create a new key remap
2. **Remove mapping** - Delete an existing remap
3. **List mappings** - View all configured remaps
4. **Toggle mapping** - Enable/disable a mapping

**Block Keys (Gaming):**
5. **Block a key** - Completely disable a key (useful for gaming)
6. **Unblock a key** - Re-enable a blocked key
7. **List blocked keys** - View all blocked keys
8. **Toggle blocked key** - Enable/disable a key block

**Control:**
- **S** - Start remapper (activate all mappings and blocks)
- **X** - Stop remapper (deactivate all)
- **W** - Save configuration to `key_remap_config.json`
- **L** - Load configuration from config file
- **K** - Show available keys
- **0** - Exit

### Key Name Format

Keys can be specified as:
- Single keys: `a`, `f1`, `escape`, `space`
- Combinations: `ctrl+a`, `shift+f1`, `ctrl+shift+escape`

#### Available Key Names

| Category | Keys |
|----------|------|
| Letters | `a` - `z` |
| Numbers | `0` - `9` |
| Function | `f1` - `f12` |
| Modifiers | `ctrl`, `lctrl`, `rctrl`, `shift`, `lshift`, `rshift`, `alt`, `lalt`, `ralt`, `win` |
| Navigation | `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown` |
| Special | `escape`, `tab`, `capslock`, `space`, `enter`, `backspace`, `delete`, `insert` |
| Numpad | `num0` - `num9`, `numplus`, `numminus`, `nummultiply`, `numdivide` |
| Punctuation | `semicolon`, `comma`, `period`, `slash`, `backslash`, `quote`, `grave`, `lbracket`, `rbracket` |

### Example Mappings

| Source | Target | Description |
|--------|--------|-------------|
| `capslock` | `escape` | Caps Lock acts as Escape (popular for Vim users) |
| `ctrl+j` | `down` | Ctrl+J acts as Down arrow |
| `f1` | `ctrl+s` | F1 saves the document |
| `ralt` | `ctrl` | Right Alt acts as Control |

### Example Blocked Keys (Gaming)

| Key | Use Case |
|-----|----------|
| `/` | Prevent accidentally opening chat in games |
| `win` | Prevent Windows key from minimizing your game |
| `alt+tab` | Prevent accidental window switching |
| `escape` | Prevent accidental pause menu in some games |

## Configuration File

Mappings and blocked keys are saved to `key_remap_config.json`:

```json
{
    "mappings": [
        {
            "source": "CAPSLOCK",
            "target": "ESCAPE",
            "enabled": true,
            "description": "Caps Lock to Escape"
        }
    ],
    "blocked_keys": [
        {
            "key": "/",
            "enabled": true,
            "description": "Block slash key during gaming"
        }
    ]
}
```

## Troubleshooting

### Remapper doesn't work in games

1. **Run as Administrator** - Right-click the script and select "Run as administrator"
2. Some anti-cheat systems may block keyboard hooks - this is by design for security

### Keys not being remapped

1. Check that the remapper status shows "ACTIVE"
2. Verify your mapping is enabled (not disabled)
3. Check `key_remapper.log` for error messages

### Program crashes

1. Check `key_remapper.log` for error details
2. Ensure you're using Python 3.8 or higher
3. Make sure you're on Windows (not Linux/Mac)

## Technical Details

- Uses `SetWindowsHookEx` with `WH_KEYBOARD_LL` for low-level keyboard interception
- Injects replacement keys using `SendInput` API
- Marks injected events to prevent infinite loops
- Thread-safe design with proper locking

## Limitations

- Windows only (uses Windows-specific APIs)
- Some games with kernel-level anti-cheat may not work
- Cannot remap mouse buttons (keyboard only)
- Cannot remap keys used by Windows itself (e.g., Ctrl+Alt+Del)

## License

MIT License - Feel free to use and modify as needed.
