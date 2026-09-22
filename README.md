# Windows Key Remapper

A free, robust keyboard key remapping tool for Windows 11 (also works on Windows 10).

Easily customize and remap keys:

<img width="562" height="493" alt="image" src="https://github.com/user-attachments/assets/2f326245-c250-49d1-8a04-a939c8174ec6" />

Block keys to prevent unintentional keypress:

<img width="564" height="497" alt="image" src="https://github.com/user-attachments/assets/f243ee04-1cc7-428e-b07f-d6e8ffcf7355" />

Complete Co-Pilot Key Remapping & Customization (Or disable forever):

<img width="575" height="582" alt="image" src="https://github.com/user-attachments/assets/a26c7f3c-6eb3-433c-bc15-4edad4f805d8" />

Option to auto-start at launch for uninterruped remapping and key blocking:

<img width="581" height="599" alt="image" src="https://github.com/user-attachments/assets/34bb324d-f407-4ece-9f4e-0d6b9ed7bd9c" />

**Version 2.5.1** | Built by Li Fan, 2026

📥 **Download**: Grab `KeyRemapper.exe` from the
[latest release](https://github.com/linkmodo/key_remapper/releases/latest) — a single file, no
Python needed. Windows will show a SmartScreen warning the first time —
[here's why, and what to click](#-windows-smartscreen-warning).

Runs as a normal user. Administrator rights are only needed if you want it to affect
windows that themselves run elevated (some games, Task Manager, etc.).

> *Created out of frustration at being unable to disable or remap keys within a particular game.*

## ✨ What's New in Version 2.5.1

- **A proper key reference** — 📋 Show Keys now opens every key name grouped by category
  (letters, modifiers, navigation, punctuation, numpad, media, browser, mouse…) with a
  plain-English description, the alternative names each key accepts, and a search box
- **⌨ beside every key field** in Add Mapping and Block Key opens the same list, and
  clicking keys fills the field for you: click `ctrl`, then `s`, and the field reads
  `ctrl+s`. *Remove last* and *Clear* undo mistakes; mouse buttons are greyed out where
  they can't be used

## ✨ What's New in Version 2.5

- **Type text that ignores your keyboard layout** — a new *Type text* action sends
  characters instead of keys, so switching between, say, English and Russian no longer
  changes what a remapped key types. Map Right Ctrl to `.` and Shift+Right Ctrl to `,`
  and you have a dedicated period/comma key in every layout.
  See [Type text](#-type-text-layout-independent)
- **Basic text expansion for free** — the same action types whole strings: an email
  address, a signature, a snippet
- **A switch to pause it all** — Settings → *Typing text* turns every text rule off and
  on again at once; the rules are kept and show as *(off)* while paused
- **Clearer buttons** — whichever of Start/Stop is inactive keeps readable text on a
  darker fill, and gray buttons now light up blue on hover instead of a barely
  different gray
- **127 unit tests**, up from 104

## ✨ What's New in Version 2.4

- **A key can now launch an app** — set a mapping's action to *Launch a program or
  app* and pick Calculator, File Explorer, Terminal and friends from a list, browse
  for any `.exe`, or paste a `shell:AppsFolder\…` link for a Store app.
  *Open a website* does the same for URLs. See [Launch an app from a key](#-launch-an-app-from-a-key)
- **A picker for volume, media and function keys** — Mute, Volume Up/Down, Play/Pause,
  F1–F24, Copy/Paste and the browser keys are two clicks away instead of a name you
  had to know
- **Keys with no name are mappable** — 🎯 Detect writes `vk0x5D` for anything exotic
  your keyboard sends instead of giving up. This is what makes most Fn combinations
  usable, since Fn itself is invisible — see [The Fn key](#-the-fn-key)
- **Detect shows the raw hardware code** (`vk 0x7B · scan 0x58`), which is the only way
  to tell two keys that share a virtual key code apart
- **Only one copy runs at a time** — launching the app while it sits in the tray reopens
  that window instead of installing a second keyboard hook
- **It says when it hides** — minimising to the tray shows a notification once per run,
  so a hidden app never looks like it crashed
- **104 unit tests**, up from 58

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
- **Launch Apps and Websites**: Point a key at Calculator, any `.exe`, a Store app or a URL
- **Layout-Independent Text**: Type characters or whole strings that come out the same in every keyboard layout
- **Multimedia Keys**: Mute, volume, play/pause, track skip and the browser keys, from a picker
- **Key Blocking**: Completely disable specific keys to prevent accidental presses during gaming (e.g., block `/` key)
- **Copilot Key Control**: Detect and repurpose the dedicated Copilot key found on 2024+ laptops
- **Per-App Profiles**: Limit any rule to a single executable
- **Dual-Role Keys**: One key that taps one thing and holds another
- **Pause Hotkey**: Suspend everything without stopping the remapper
- **Mouse Side Buttons**: `mouse3`/`mouse4`/`mouse5` as remap sources
- **Single Instance**: a second launch reopens the existing window instead of double-hooking
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
   | v2.5.1 | `32f4f100586954ee5db25c2165b7d7b380eb7a9ce799d9f1f89061524287bf1e` |
   | v2.5.0 | `e8f3a50413c93744e3cc36e0f9957dc637adb942d1a468cdd1b1044ad94b2f55` |
   | v2.4.0 | `2cb3995c8c40374c681e4a76bd0914e9841721cf86af7ca76ddf64d450a0342b` |
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

### ▶ Launch an app from a key

A mapping does not have to send keys. In **Add Mapping**, *What should it do?* offers:

| Action | What you fill in |
|--------|------------------|
| **Send other key(s)** | A key or combination — with a picker for volume, media, function and browser keys |
| **Type text** | Characters to type, whatever the keyboard layout — see [Type text](#-type-text-layout-independent) |
| **Launch a program or app** | Pick from the common apps list, **📂 Browse** for an `.exe`, or type anything the shell can open |
| **Open a website** | Any URL — it opens in your default browser |

**▶ Test** runs the action once without pressing the key, so you can check a path
before committing to it.

Anything these accept:

| You type | What happens |
|----------|--------------|
| `calc.exe` | An executable on `PATH` — this one opens the Windows Calculator |
| `C:\Tools\thing.exe --flag` | A full path, arguments included |
| `D:\notes\todo.md` | Any document or folder, opened with its default program |
| `ms-settings:` | A Windows Settings page (`ms-settings:bluetooth`, …) |
| `shell:AppsFolder\<app-id>` | A Microsoft Store / packaged app |

> To find a Store app's id: run `explorer shell:AppsFolder`, right-click the app →
> *Create shortcut*, then read the target off the shortcut on your desktop.

So the classic setup — Fn+F12 opens the calculator — is: **Add Mapping** → 🎯 Detect →
press Fn+F12 → *Launch a program or app* → **Calculator** → **Add**.

Launching happens on a worker thread, never inside the keyboard hook: a low-level hook
that takes longer than `LowLevelHooksTimeout` is silently removed by Windows.

### ✎ Type text (layout-independent)

**Why it exists.** *Send other key(s)* sends a virtual key — a *position* on the keyboard.
The app receiving it turns that into a character using whatever layout is active. So a
rule sending `period` types `.` in English but `ю` in Russian: the remap follows the layout.
That is how every virtual-key remapper behaves, PowerToys included.

*Type text* sends the **characters themselves** (`SendInput` with `KEYEVENTF_UNICODE`),
which no layout can reinterpret.

| Source | Type text | Result |
|--------|-----------|--------|
| `rctrl` | `.` | Right Ctrl is a period key in every layout |
| `shift+rctrl` | `,` | …and Shift+Right Ctrl a comma |
| `ctrl+alt+m` | `me@example.com` | Text expansion |
| `f13` | `—` | A character your layout has no key for |

**▶ Test** in the dialog types the text into a box right there, so you can see exactly
what comes out. Whitespace is kept — `, ` (comma space) and a lone space are valid.

Things to know:

- **Shift does not change typed text** — it is a literal character, not a key. Give the
  shifted character its own rule, as with `shift+rctrl` above.
- **Holding the key repeats the text**, the same as holding a normal key.
- **Games that read raw keyboard input won't see it.** Typed characters arrive as text
  (`WM_CHAR`), not as key presses. This is a typing feature, not a gaming one — use
  *Send other key(s)* for games.
- **Settings → Typing text** pauses every text rule at once. The keys go back to normal,
  the rules are kept, and the list marks them *(off)* until you switch it back on.

### ⌨️ The Fn key

**Fn is not supported as a modifier, and it is worth explaining why.**

On the overwhelming majority of keyboards, the Fn key never reaches Windows at all. It is
handled inside the keyboard's own controller, which simply emits a *different key* for the
combination. Pressing Fn+F12 does not produce "Fn plus F12" — it produces `volumeup`, or
plain `f12`, or a code with no name, depending on the hardware. No application can observe
a key the hardware never sends, and a low-level hook is no exception.

So there is no `fn` you can type in a rule, and 🎯 Detect cannot record Fn on its own.
**Fn key mapping is limited to what follows.**

**What does work — map what the combination actually sends:**

1. **Add Mapping** → 🎯 **Detect** on the source
2. Hold **Fn** and tap **F12** — press the whole combination
3. The dialog records exactly what arrived — `VOLUMEUP`, `F12`, `vk0x97`, … — and shows
   the raw code underneath (`vk 0x7B · scan 0x58`)
4. Give it a target or an app, and click **Add**

That covers the common case completely: if Fn+F12 sends `volumeup`, then mapping `volumeup`
to the Calculator gives you exactly "Fn+F12 opens the Calculator".

**The one case it cannot cover:** if Fn+F12 and a plain F12 arrive as *byte-for-byte the
same event*, nothing can distinguish them — not this app, not any other. The Detect dialog
shows the raw code precisely so you can check: press each one and compare. Different codes
mean you are fine.

#### Keys with no name

Keyboards send codes this app has no friendly name for, especially under Fn. 🎯 Detect
writes those as `vk0x5D` (or `vk93` — decimal works too) and they can be used anywhere a
key name can. Nothing your keyboard sends is off-limits.

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

**💡 Tip**: Use the 🎯 Detect buttons in the GUI to automatically capture key presses, or
click **⌨** beside any key field to pick names from a searchable list.

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
| Media | `playpause`, `nexttrack`, `prevtrack`, `mediastop`, `mute`, `volumeup`, `volumedown`, `calculator`, `mail`, `mediaselect`, `launchapp1`, `launchapp2`, `sleep` |
| Browser | `browserback`, `browserforward`, `browserrefresh`, `browserhome`, `browsersearch`, `browserstop`, `browserfavorites` |
| Raw codes | `vk0x5D` / `vk93` — any key with no friendly name |
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
| `f9` | `mute` | F9 mutes the system volume |
| `f10` / `f11` | `volumedown` / `volumeup` | Media keys on a keyboard that lacks them |
| `f12` | launch `calc.exe` | F12 opens the Windows Calculator |
| `volumeup` | launch `calc.exe` | Whatever Fn+F12 sends on your laptop, repurposed |
| `mouse5` | open `https://claude.ai` | Side button opens a site |

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
    "version": 6,
    "mappings": [
        {
            "source": "CAPSLOCK",
            "target": "ESCAPE",
            "action": "keys",
            "value": "",
            "hold": "CTRL",
            "app": "",
            "enabled": true,
            "description": "Caps Lock to Escape"
        },
        {
            "source": "F12",
            "target": "",
            "action": "launch",
            "value": "calc.exe",
            "hold": "",
            "app": "",
            "enabled": true,
            "description": "Calculator"
        },
        {
            "source": "RCTRL",
            "target": "",
            "action": "text",
            "value": ".",
            "hold": "",
            "app": "",
            "enabled": true,
            "description": "Period in every layout"
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
        "start_on_launch": false,
        "type_text_enabled": true
    }
}
```

A mapping's `action` is `keys` (send `target`), `text` (type `value` literally), or
`launch` / `url` (open `value`). `type_text_enabled` is the Settings switch for text rules.
Copilot `mode` is one of `disable`, `keys`, `launch`, `url` or `passthrough`.
Older config files load unchanged — missing fields and sections fall back to defaults.

## Tests

```powershell
python -m unittest discover -s tests
```

135 tests drive the rule engine directly (no real hooks, no keyboard input needed), covering
remaps, blocks, per-app scoping, dual-role keys, the pause hotkey, the Copilot chord, the mouse
hook, app-launching mappings, layout-independent text (including the exact `SendInput`
events it produces), raw key codes, the key reference, the single-instance guard and config
round-tripping — including that configs written by earlier versions still load.

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

### Fn+F12 (or any Fn combination) will not detect

Fn is not a modifier this app can see — your keyboard handles it internally and never
tells Windows. That is normal and it is the majority case. Detect the **combination**
rather than the Fn key: 🎯 Detect, then hold Fn and tap F12, and whatever your keyboard
actually sends is recorded and mappable. [Full explanation](#-the-fn-key).

### The app opens and immediately disappears

It did not close — it minimised to the system tray, because **Settings → "Start hidden in
the system tray"** is ticked. Windows 11 hides new tray icons behind the `^` arrow on the
taskbar; click it, then drag the K icon onto the taskbar to keep it visible. Untick that
setting if you would rather see the window on every launch. Launching the app again while
it is hidden reopens the window rather than starting a second copy.

### The app I launched from a key did not open

1. Click **▶ Test** in the mapping dialog — it runs the same code path and fails the same way
2. A Store app usually needs `shell:AppsFolder\<app-id>` rather than an `.exe` path
3. Check `%APPDATA%\KeyRemapper\key_remapper.log` — every launch and every failure is logged

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
- Injects replacement keys using `SendInput` API, as virtual keys — so the active layout
  decides the character, exactly as for a physical key
- *Type text* rules instead send `KEYEVENTF_UNICODE` packets (`wVk = 0`, the character in
  `wScan`), which bypass the layout entirely; the whole string goes in one `SendInput` call
- Marks injected events (`dwExtraInfo`) to prevent infinite loops
- Combinations are matched as (modifier families, main key) signatures
- Slow actions (launching apps, opening URLs) run on a worker thread — a low-level hook that
  takes longer than `LowLevelHooksTimeout` is silently removed by Windows
- Thread-safe design with proper locking

## Limitations

- Windows only (uses Windows-specific APIs)
- Some games with kernel-level anti-cheat may not work
- Left and right mouse buttons are deliberately not remappable, and mouse buttons
  cannot be a target
- Cannot remap keys used by Windows itself (e.g., Ctrl+Alt+Del)
- **The Fn key cannot be used as a modifier.** Virtually no keyboard reports it to
  Windows; map what the combination actually sends instead ([why](#-the-fn-key))
- Two keys that send an identical virtual key code *and* scan code cannot be told apart

## Support this project

Built by **Li Fan**, 2026. If Key Remapper saved you some frustration, you're very welcome to
[buy me a coffee ☕](https://paypal.me/lifan) — there's also a Donate button in the app's
**ℹ️ About** dialog.

Bug reports and feature requests are welcome on the
[issue tracker](https://github.com/linkmodo/key_remapper/issues).

## License

MIT License - Feel free to use and modify as needed.
