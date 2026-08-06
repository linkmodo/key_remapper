# Windows Key Remapper

A robust, gaming-compatible key remapping tool for Windows 11 (also works on Windows 10).

**Version 2.3** | Built by Li Fan, 2025

📥 **Download**: Grab `KeyRemapper.exe` from the
[latest release](https://github.com/linkmodo/key_remapper/releases/latest) — a single file, no
Python needed. Windows will show a SmartScreen warning the first time —
[here's why, and what to click](#-windows-smartscreen-warning).

Runs as a normal user. Administrator rights are only needed if you want it to affect
windows that themselves run elevated (some games, Task Manager, etc.).

> *Created out of frustration at being unable to disable or remap keys within a particular game.*

## ✨ What's New in Version 2.3

- **Scrollbars only appear when there is something to scroll** — every panel hides its
  scrollbar while the content fits
- **Reset everything to defaults** — one button in Settings clears all rules, the Copilot
  action and every setting, and removes the logon entry
- **Nothing is blocked out of the box.** A stale development config meant `/` could arrive
  pre-blocked; a fresh install now starts completely empty
- **Rewritten Help/About** — leads with what the app does, with the project link and a
  ☕ Donate button at the end

## ✨ What's New in Version 2.2

- **Give the Copilot key back its old job**: one click turns it into **Right Alt**, **Windows**,
  **Menu ▤** or **Right Ctrl** — whichever key your laptop sacrificed for it
- **Per-app profiles**: scope any mapping or block to a single executable, so `F1` can mean one
  thing in your game and nothing anywhere else
- **Tap vs hold (dual-role keys)**: CapsLock can send Escape when tapped and act as Ctrl when held
- **Pause hotkey**: suspend every mapping without stopping the remapper, from a hotkey or the tray
- **Mouse side buttons** (`mouse3`/`mouse4`/`mouse5`) usable as sources
- **Run at logon** and **start hidden in the tray**, with a new **Settings** tab
- **Edit mappings in place** (double-click a row) with conflict warnings before you overwrite
- **🎯 Detect now uses the low-level hook**, so Win, F13-F24 and Copilot combinations are
  detectable instead of "type it manually"
- **58 unit tests** covering the rule engine, including the Copilot chord and the mouse hook

## ✨ What's New in Version 2.1

- **Copilot Key tab**: detect what your laptop's Copilot key actually sends, then disable it,
  send different keys, or launch any program, file or website — see [Copilot Key](#-copilot-key)
- **Modifier combinations now work**: `ctrl+`/`shift+`/`alt+`/`win+` combos are matched by
  modifier *family*, so the left/right key the hardware reports no longer matters.
  (Previously any combination involving a modifier silently never fired.)
- **Config and log moved to `%APPDATA%\KeyRemapper\`** so settings survive updates and work
  from a one-file `.exe`. An existing `key_remap_config.json` next to the app is migrated once.
- **Hook runs on its own thread**: a busy or blocked UI can no longer stall your keyboard,
  and the text-mode menu works properly.
- **Media & browser keys** available as remap targets (`playpause`, `mute`, `calculator`, …).
- **Real logging again** — every action goes to `%APPDATA%\KeyRemapper\key_remapper.log`.

## Version 2.0

- **Extended Function Keys (F13-F24)**: Full support for extended function keys including F13-F24
- **Interactive Key Detection**: 🎯 Detect buttons to capture key presses in real-time
- **Auto-Save**: All changes are automatically saved - no need to manually save config
- **Improved Key Capture**: Better handling of modifier keys and combinations

## Features

- **Modern GUI**: Clean, dark-themed interface built with customtkinter
- **Gaming Compatible**: Uses low-level Windows hooks (`SetWindowsHookEx`) that work with most games and applications
- **Key Combinations**: Remap single keys to key combinations (e.g., `F1` → `Ctrl+S`, `F2` → `Ctrl+Shift+S`)
- **Key Blocking**: Completely disable specific keys to prevent accidental presses during gaming (e.g., block `/` key)
- **Copilot Key Control**: Detect and repurpose the dedicated Copilot key found on 2024+ laptops
- **Per-App Profiles**: Limit any rule to a single executable
- **Dual-Role Keys**: One key that taps one thing and holds another
- **Pause Hotkey**: Suspend everything without stopping the remapper
- **Mouse Side Buttons**: `mouse3`/`mouse4`/`mouse5` as remap sources
- **Interactive Key Detection**: Click 🎯 Detect buttons to capture key presses automatically
- **System Tray**: Minimize to system tray while remapper runs in the background
- **Standalone Executable**: Build a single `.exe` file - no Python installation required
- **Auto-Save Configuration**: Changes are saved automatically to JSON file
- **Toggle Mappings**: Enable/disable individual mappings or blocked keys without removing them
- **Logging**: All actions logged to `%APPDATA%\KeyRemapper\key_remapper.log` for troubleshooting

## Requirements

### For Running from Source
- Windows 10 or Windows 11
- Python 3.8 or higher

### For Executable
- Windows 10 or Windows 11

Administrator privileges are **optional**. Elevate only if you need the remapper to reach
windows that run elevated themselves.

## Installation

### Option 1: Download the executable (easiest)

1. Download `KeyRemapper.exe` from the
   [latest release](https://github.com/linkmodo/key_remapper/releases/latest)
2. Double-click it. See the SmartScreen note below for the first-run warning.

### Option 2: Run from Source

1. Clone or download this repository
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the GUI:
   ```powershell
   python key_remapper_gui.py
   ```

### Option 3: Build Standalone Executable

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. Run the build script:
   ```powershell
   python build.py
   ```
3. Find the executable at `dist/KeyRemapper.exe`
4. Double-click to run

## ⚠️ Windows SmartScreen warning

The first time you run the downloaded `.exe`, Windows shows a blue box:

> **Windows protected your PC**
> Microsoft Defender SmartScreen prevented an unrecognised app from starting.

**To run it anyway: click "More info", then "Run anyway".**

### Why it happens

The executable is **not code-signed**. A signing certificate costs money per year, and this is a
free hobby project. SmartScreen flags *every* unsigned executable that it hasn't seen downloaded
many times before — it is a statement about the certificate and download count, not about
whether anything is wrong with the file. The warning fades for everyone as more people download
a given release.

Some browsers also block the download itself for the same reason. In Edge or Chrome, choose
**Keep** → **Keep anyway** in the downloads bar.

### Don't want to trust a stranger's binary?

Fair. You have three options, in order of paranoia:

1. **Verify the checksum** — confirm your download is byte-for-byte the file published here:

   ```powershell
   Get-FileHash .\KeyRemapper.exe -Algorithm SHA256
   ```

   | Release | SHA-256 |
   |---------|---------|
   | v2.3.0 | `883f407b5b61655076cc8e57d2bb50c1d2f74ba9e837bf16b2dfc09e34e4eff9` |
   | v2.2.0 | `44e158dd07c9a9b9d6c1ca109fbe19b2d546778de95515fb5bf35c52805b48a0` |

   This proves the file wasn't tampered with in transit. It does not prove the code is
   trustworthy — for that, see below.

2. **Read the source** — it's all in this repository, about 2,000 lines of Python, and the
   `.exe` is just [`build.py`](build.py) running PyInstaller over it.

3. **Build it yourself** — Option 3 above. Then no download, no warning, no trust required.

### What the app actually does that looks suspicious

A key remapper is, by construction, indistinguishable from a keylogger to a scanner: it installs
a global `WH_KEYBOARD_LL` hook and therefore sees every keystroke you type. That is the whole
mechanism — there is no way to remap keys without it. So here is exactly what it does with them:

- **Your typing is never recorded.** Keystrokes are matched against your rules in memory and
  then forgotten. There is no logging in the key-handling path
  ([`_handle_key_event`](key_remapper.py)) apart from an error handler.
- **One exception, and it's one you trigger:** when you press 🎯 Detect, the key code you
  deliberately capture is written to the log so the feature can be debugged — e.g.
  `Chord captured: ('shift', 'win') + 0x86`. Nothing else you type ever reaches the log.
- **The log otherwise records actions only** — "added mapping", "remapper started" — plus the
  rules you configure, which you wrote yourself.
- **No network connections.** No telemetry, no update check, no sockets anywhere in the source.
  The only outbound action is opening a URL or launching a program *you* assigned to the
  Copilot key, which hands off to your normal browser or shell.
- **It writes to two places**: `%APPDATA%\KeyRemapper\` (config + log), and — only if you tick
  "Launch when I sign in" — one `KeyRemapper` value under
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Unticking it removes the value.

Every one of these is checkable in [`key_remapper.py`](key_remapper.py); `grep` for `logger.`,
`winreg`, and `webbrowser` and you'll find the lot.

## Usage

### Running the GUI

```powershell
python key_remapper_gui.py
```

If a specific game ignores your remaps, that game is probably running elevated — start the
remapper as administrator in that case.

### 🤖 Copilot Key

The Copilot key on modern Windows laptops is **not a new scan code**. The keyboard firmware
emits a hidden chord — on virtually every OEM that chord is `Left Shift + Left Win + F23`.
That is why simply "blocking F23" does nothing useful, and why releasing the key can pop the
Start menu.

Open the **Copilot Key** tab and:

| Step | What it does |
|------|--------------|
| 🎯 **Detect** | Swallows all input until you press the Copilot key, then records the exact chord your machine sends (handles the rare `win+c` / bare-`F23` keyboards) |
| **Do nothing** | Kills the key entirely, including the Start-menu side effect |
| **Send other key(s)** | Turn it into any key or combination — `ctrl+shift+p`, `playpause`, `f13`, … |
| **Launch a program or file** | Point it at an `.exe`, document, folder or shell command |
| **Open a website** | Any URL, opened in your default browser |
| **Pass through** | Leave the key alone |

#### Give it back the key your laptop removed

Most laptops made room for the Copilot key by dropping a key you were already using. One click
puts it back:

| Button | Result |
|--------|--------|
| **Right Alt** | The Copilot key behaves as `ralt` (AltGr on international layouts) |
| **Windows** | Acts as a Windows key |
| **Menu ▤** | The context-menu key that most Copilot keyboards replaced |
| **Right Ctrl** | Acts as `rctrl` |

Modifier targets are *held* for as long as the firmware holds the chord, so `Copilot`+another key
works on keyboards that keep the chord down. Most send a single burst, which lands as a tap —
exactly what you want for Menu and Windows.

Other quick presets: *Disable it*, *Screenshot* (`win+shift+s`), *Play/Pause*, *File Explorer*.
**Apply** saves immediately; the remapper must be started (▶ Start) for the key to take effect.

> Windows 11 24H2 can also remap this key from Settings, but only to signed, MSIX-packaged
> apps. This tab works with anything on your machine.

Under the hood, when the chord fires the remapper injects an unassigned virtual key so that
releasing the still-held Windows key does not open the Start menu, virtually releases the
held modifiers, and only then performs your action — so `Shift`/`Win` never leak into the
keys it sends.

### Per-app profiles

Leave **Only in this app** empty and a rule applies everywhere. Fill in an executable name
(`game.exe` — a full path is fine, it gets reduced to the file name) and the rule only fires
while that window has focus. An app-specific rule beats a global one for the same key, so you
can have a global default and a per-game override.

The foreground executable is only looked up when at least one app-scoped rule exists, and the
answer is cached briefly — the hook stays fast.

### Tap vs hold (dual-role keys)

Fill in **When held instead** and a key gets two jobs:

| Source | Target | When held | Result |
|--------|--------|-----------|--------|
| `capslock` | `escape` | `ctrl` | Tap for Escape, hold for Ctrl — the classic Vim setup |
| `space` | `space` | `shift` | Space bar doubles as Shift |

The hold role activates as soon as you press another key while holding it, or after the
**tap vs hold threshold** (Settings tab, 250 ms by default). Hold roles need a single source
key, not a combination.

### Pause hotkey

Set one in the **Settings** tab (e.g. `ctrl+alt+f12`) to suspend every mapping without
releasing the hook — useful when a remap is fighting with an app. The status turns amber, the
tray icon turns orange, and anything currently held down is released rather than left stuck.
The tray menu has **Pause / Resume** too.

### Mouse buttons

`mouse3` (middle), `mouse4` and `mouse5` (the side buttons) can be used as **sources** for
mappings and blocks — e.g. `mouse4` → `ctrl+c`. Left and right click are deliberately not
remappable, and mouse buttons cannot be a *target*. The mouse hook is only installed when a
rule actually needs it.

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

**Copilot Key:**
9. **Configure the Copilot key** - Detect it and choose what it should do

**Control:**
- **S** - Start remapper (activate all mappings and blocks)
- **X** - Stop remapper (deactivate all)
- **P** - Pause/resume without releasing the hook
- **W** - Save configuration to `key_remap_config.json`
- **L** - Load configuration from config file
- **K** - Show available keys
- **0** - Exit

### Key Name Format

Keys can be specified as:
- Single keys: `a`, `f1`, `escape`, `space`
- Combinations: `ctrl+a`, `shift+f1`, `ctrl+shift+escape`, `win+shift+f23`

**💡 Tip**: Use the 🎯 Detect buttons in the GUI to automatically capture key presses!

#### Available Key Names

| Category | Keys |
|----------|------|
| Letters | `a` - `z` |
| Numbers | `0` - `9` |
| Function | `f1` - `f12` |
| Extended Function | `f13` - `f24` (includes Copilot key: `win+shift+f23`) |
| Modifiers | `ctrl`, `lctrl`, `rctrl`, `shift`, `lshift`, `rshift`, `alt`, `lalt`, `ralt`, `win`, `lwin`, `rwin` |
| Navigation | `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown` |
| Special | `escape`, `tab`, `capslock`, `space`, `enter`, `backspace`, `delete`, `insert`, `apps` |
| Numpad | `num0` - `num9`, `numplus`, `numminus`, `nummultiply`, `numdivide` |
| Media | `playpause`, `nexttrack`, `prevtrack`, `mediastop`, `mute`, `volumeup`, `volumedown`, `calculator`, `mail` |
| Browser | `browserback`, `browserforward`, `browserrefresh`, `browserhome`, `browsersearch` |
| Mouse (source only) | `mouse3` / `middleclick`, `mouse4`, `mouse5` |
| Punctuation | `semicolon`, `comma`, `period`, `slash`, `backslash`, `quote`, `grave`, `lbracket`, `rbracket` |

Modifiers are matched by family: a mapping written as `ctrl+a` fires for either Ctrl key.
Left/right distinctions still work when the modifier is the key being remapped (e.g. `ralt` → `ctrl`).

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
| `win+shift+f23` | The raw Copilot chord — prefer the **Copilot Key** tab, which also suppresses the Start menu |

## Configuration File

Everything is saved to `%APPDATA%\KeyRemapper\key_remap_config.json`:

```json
{
    "version": 4,
    "mappings": [
        {
            "source": "CAPSLOCK",
            "target": "ESCAPE",
            "hold": "CTRL",
            "app": "",
            "enabled": true,
            "description": "Caps Lock to Escape"
        }
    ],
    "blocked_keys": [
        {
            "key": "/",
            "app": "game.exe",
            "enabled": true,
            "description": "Block slash key during gaming"
        }
    ],
    "copilot": {
        "enabled": true,
        "modifiers": ["shift", "win"],
        "key": "f23",
        "mode": "keys",
        "value": "ralt",
        "description": "Copilot key"
    },
    "settings": {
        "toggle_hotkey": "ctrl+alt+f12",
        "tap_timeout_ms": 250,
        "run_at_startup": false,
        "start_minimized": false,
        "start_on_launch": false
    }
}
```

Copilot `mode` is one of `disable`, `keys`, `launch`, `url` or `passthrough`. Older config
files load unchanged — missing sections fall back to defaults.

## Tests

```powershell
python -m unittest discover -s tests
```

58 tests drive the rule engine directly (no real hooks, no keyboard input needed), covering
remaps, blocks, per-app scoping, dual-role keys, the pause hotkey, the Copilot chord, the mouse
hook and config round-tripping.

## Troubleshooting

### "Windows protected your PC" when I run the .exe

Click **More info → Run anyway**. The executable is not code-signed, so SmartScreen flags it —
see [Windows SmartScreen warning](#-windows-smartscreen-warning) for why, how to verify the
download's checksum, and how to build it yourself instead.

### My antivirus flagged it

Expect the occasional false positive: the app installs a global keyboard hook, which is the same
API a keylogger uses, and PyInstaller one-file executables are themselves a common heuristic
trigger. The [SmartScreen section](#-windows-smartscreen-warning) documents exactly what the app
does with your keystrokes and where it writes. Building from source avoids the packed-executable
heuristic entirely.

### Remapper doesn't work in games

1. If the game runs elevated, run the remapper as administrator too
2. Some anti-cheat systems block keyboard hooks - this is by design for security

### Keys not being remapped

1. Check that the remapper status shows "ACTIVE"
2. Verify your mapping is enabled (not disabled)
3. Check `%APPDATA%\KeyRemapper\key_remapper.log` for error messages

### The Copilot key still opens Copilot

1. Use 🎯 **Detect** on the Copilot Key tab — your keyboard may send a different chord
2. Make sure the remapper is started, and that the tab does not say "pass through"

### Program crashes

1. Check `%APPDATA%\KeyRemapper\key_remapper.log` for error details
2. Ensure you're using Python 3.8 or higher
3. Make sure you're on Windows (not Linux/Mac)

## Technical Details

- Uses `SetWindowsHookEx` with `WH_KEYBOARD_LL` for low-level keyboard interception
- The hook is installed and pumped on a dedicated thread, so UI work can never stall input
- Injects replacement keys using `SendInput` API
- Marks injected events (`dwExtraInfo`) to prevent infinite loops
- Combinations are matched as (modifier families, main key) signatures
- Slow actions (launching apps, opening URLs) run on a worker thread — a low-level hook that
  takes longer than `LowLevelHooksTimeout` is silently removed by Windows
- Thread-safe design with proper locking

## Limitations

- Windows only (uses Windows-specific APIs)
- Some games with kernel-level anti-cheat may not work
- Cannot remap mouse buttons (keyboard only)
- Cannot remap keys used by Windows itself (e.g., Ctrl+Alt+Del)

## Support this project

Built by **Li Fan**, 2025. If Key Remapper saved you some frustration, you're very welcome to
[buy me a coffee ☕](https://paypal.me/lifan) — there's also a Donate button in the app's
**ℹ️ About** dialog.

Bug reports and feature requests are welcome on the
[issue tracker](https://github.com/linkmodo/key_remapper/issues).

## License

MIT License - Feel free to use and modify as needed.
