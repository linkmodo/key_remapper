"""
Tests for the key remapper engine.

These drive ``_handle_key_event`` directly instead of installing a real hook, so
the whole rule engine - remaps, blocks, dual-role keys, per-app profiles, the
pause hotkey and the Copilot key - is testable without touching the keyboard.

Run with:  python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import key_remapper as kr  # noqa: E402


LSHIFT = int(kr.VirtualKey.VK_LSHIFT)
LCTRL = int(kr.VirtualKey.VK_LCONTROL)
LWIN = int(kr.VirtualKey.VK_LWIN)
F13 = int(kr.VirtualKey.VK_F13)
F23 = int(kr.VirtualKey.VK_F23)
CAPS = int(kr.VirtualKey.VK_CAPITAL)
ESC = int(kr.VirtualKey.VK_ESCAPE)
APPS = int(kr.VirtualKey.VK_APPS)
RALT = int(kr.VirtualKey.VK_RMENU)
KEY_A = 0x41
KEY_J = 0x4A


class FakeRemapper(kr.KeyRemapper):
    """A remapper that records injected keys instead of sending them."""

    def __init__(self):
        super().__init__()
        self.sent = []
        self.clock = 1000.0

    def _send_key(self, vk_code, key_up=False):
        self.sent.append((vk_code, 'up' if key_up else 'down'))

    def now(self):
        return self.clock

    def down(self, vk):
        return self._handle_key_event(vk, True, False)

    def up(self, vk):
        return self._handle_key_event(vk, False, True)

    def tap(self, vk):
        return self.down(vk), self.up(vk)


class MonotonicPatch:
    """Freeze/advance time.monotonic inside the module under test."""

    def __init__(self, remapper):
        self.remapper = remapper
        self.original = None

    def __enter__(self):
        self.original = kr.time.monotonic
        kr.time.monotonic = self.remapper.now
        return self

    def __exit__(self, *exc):
        kr.time.monotonic = self.original


class ParsingTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_parses_combination_with_modifiers_first(self):
        self.assertEqual(
            self.remapper.parse_key_string('a+ctrl'),
            (int(kr.VirtualKey.VK_CONTROL), KEY_A)
        )

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            self.remapper.parse_key_string('notakey')

    def test_signature_groups_modifiers_by_family(self):
        generic = kr.combo_signature((int(kr.VirtualKey.VK_SHIFT), F23))
        specific = kr.combo_signature((LSHIFT, F23))
        self.assertEqual(generic, specific)

    def test_signature_of_modifier_only_combo(self):
        families, main = kr.combo_signature((int(kr.VirtualKey.VK_CONTROL), LSHIFT))
        self.assertEqual(families, frozenset({'ctrl'}))
        self.assertEqual(main, LSHIFT)

    def test_empty_combination_rejected(self):
        with self.assertRaises(ValueError):
            kr.combo_signature(())


class RemapTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_single_key_remap_suppresses_and_injects(self):
        self.remapper.add_mapping('f13', 'a')

        self.assertTrue(self.remapper.down(F13))
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

        self.assertTrue(self.remapper.up(F13))
        self.assertEqual(self.remapper.sent[-1], (KEY_A, 'up'))

    def test_combination_matches_side_specific_modifiers(self):
        """The hook reports VK_LCONTROL; the user typed the generic 'ctrl'."""
        self.remapper.add_mapping('ctrl+shift+a', 'f13')

        self.assertFalse(self.remapper.down(LCTRL))
        self.assertFalse(self.remapper.down(LSHIFT))
        self.assertTrue(self.remapper.down(KEY_A))
        self.assertEqual(self.remapper.sent, [(F13, 'down')])

    def test_unmapped_key_passes_through(self):
        self.remapper.add_mapping('f13', 'a')
        self.assertFalse(self.remapper.down(KEY_J))
        self.assertEqual(self.remapper.sent, [])

    def test_blocked_key_is_swallowed_both_ways(self):
        self.remapper.block_key('f13')
        self.assertTrue(self.remapper.down(F13))
        self.assertTrue(self.remapper.up(F13))
        self.assertEqual(self.remapper.sent, [])

    def test_disabled_mapping_is_ignored(self):
        self.remapper.add_mapping('f13', 'a')
        self.remapper.toggle_mapping('f13')
        self.assertFalse(self.remapper.down(F13))
        self.assertEqual(self.remapper.sent, [])

    def test_mouse_button_source_is_recognised(self):
        self.remapper.add_mapping('mouse4', 'a')
        self.assertTrue(self.remapper._needs_mouse_hook)
        self.assertTrue(self.remapper.down(int(kr.VirtualKey.VK_XBUTTON1)))
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

    def test_mouse_hook_not_needed_without_mouse_rules(self):
        self.remapper.add_mapping('f13', 'a')
        self.assertFalse(self.remapper._needs_mouse_hook)


class MouseHookTests(unittest.TestCase):
    """Drives _mouse_callback with fabricated hook structures."""

    def setUp(self):
        self.remapper = FakeRemapper()

    def _event(self, message, x_button=0):
        struct = kr.MSLLHOOKSTRUCT()
        struct.mouseData = x_button << 16
        struct.flags = 0
        struct.dwExtraInfo = 0
        return self.remapper._mouse_callback(0, message, kr.ctypes.pointer(struct))

    def test_side_button_is_remapped(self):
        self.remapper.add_mapping('mouse4', 'a')
        self.assertEqual(self._event(kr.WM_XBUTTONDOWN, kr.XBUTTON1), 1)
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

        self.assertEqual(self._event(kr.WM_XBUTTONUP, kr.XBUTTON1), 1)
        self.assertEqual(self.remapper.sent[-1], (KEY_A, 'up'))

    def test_second_side_button_is_distinct(self):
        self.remapper.add_mapping('mouse4', 'a')
        self.assertNotEqual(self._event(kr.WM_XBUTTONDOWN, kr.XBUTTON2), 1)
        self.assertEqual(self.remapper.sent, [])

    def test_middle_button_can_be_blocked(self):
        self.remapper.block_key('mouse3')
        self.assertEqual(self._event(kr.WM_MBUTTONDOWN), 1)
        self.assertEqual(self._event(kr.WM_MBUTTONUP), 1)

    def test_mouse_movement_is_ignored_cheaply(self):
        self.remapper.add_mapping('mouse4', 'a')
        self.assertNotEqual(self._event(kr.WM_MOUSEMOVE), 1)
        self.assertEqual(self.remapper.sent, [])

    def test_our_own_injected_clicks_are_skipped(self):
        self.remapper.block_key('mouse3')
        struct = kr.MSLLHOOKSTRUCT()
        struct.flags = kr.LLKHF_INJECTED
        struct.dwExtraInfo = self.remapper._injection_marker
        result = self.remapper._mouse_callback(0, kr.WM_MBUTTONDOWN, kr.ctypes.pointer(struct))
        self.assertNotEqual(result, 1)

    def test_mouse_button_rejected_as_a_target(self):
        self.assertFalse(self.remapper.add_mapping('f13', 'mouse4'))
        self.assertFalse(self.remapper.add_mapping('f13', 'a', hold='mouse5'))

    def test_mouse_source_combines_with_keyboard_modifiers(self):
        self.remapper.add_mapping('ctrl+mouse4', 'a')
        self.remapper.down(LCTRL)
        self.assertEqual(self._event(kr.WM_XBUTTONDOWN, kr.XBUTTON1), 1)
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])


class ConflictTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_duplicate_source_is_reported(self):
        self.remapper.add_mapping('f13', 'a')
        self.assertIn('already remapped', self.remapper.find_conflict('f13'))

    def test_blocked_key_conflicts_with_new_mapping(self):
        self.remapper.block_key('ctrl+f13')
        self.assertIn('already blocked', self.remapper.find_conflict('ctrl+f13'))

    def test_same_key_in_different_apps_does_not_conflict(self):
        self.remapper.add_mapping('f13', 'a', app='game.exe')
        self.assertIsNone(self.remapper.find_conflict('f13'))
        self.assertIsNone(self.remapper.find_conflict('f13', app='other.exe'))

    def test_editing_a_rule_does_not_conflict_with_itself(self):
        self.remapper.add_mapping('f13', 'a')
        keys = self.remapper.parse_key_string('f13')
        self.assertIsNone(self.remapper.find_conflict('f13', ignore=(keys, '')))


class PerAppTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()
        self.foreground = ''
        self.remapper._foreground_exe = lambda: self.foreground

    def test_rule_only_applies_in_its_app(self):
        self.remapper.add_mapping('f13', 'a', app='game.exe')

        self.foreground = 'notepad.exe'
        self.assertFalse(self.remapper.down(F13))
        self.assertEqual(self.remapper.sent, [])

        self.foreground = 'game.exe'
        self.assertTrue(self.remapper.down(F13))
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

    def test_app_rule_wins_over_global_rule(self):
        self.remapper.add_mapping('f13', 'a')
        self.remapper.add_mapping('f13', 'j', app='game.exe')

        self.foreground = 'game.exe'
        self.remapper.down(F13)
        self.assertEqual(self.remapper.sent, [(KEY_J, 'down')])

    def test_global_rule_still_applies_in_other_apps(self):
        self.remapper.add_mapping('f13', 'a')
        self.remapper.add_mapping('f13', 'j', app='game.exe')

        self.foreground = 'notepad.exe'
        self.remapper.down(F13)
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

    def test_app_names_are_normalised(self):
        self.remapper.add_mapping('f13', 'a', app=r'C:\Games\Game.EXE')
        self.foreground = 'game.exe'
        self.assertTrue(self.remapper.down(F13))

    def test_foreground_lookup_skipped_without_app_rules(self):
        remapper = FakeRemapper()
        remapper.add_mapping('f13', 'a')
        self.assertEqual(remapper._foreground_exe(), '')


class DualRoleTests(unittest.TestCase):
    """CapsLock -> Escape when tapped, Ctrl while held."""

    def setUp(self):
        self.remapper = FakeRemapper()
        self.remapper.add_mapping('capslock', 'escape', hold='ctrl')
        self.remapper.apply_settings(kr.Settings(tap_timeout_ms=250))

    def test_quick_tap_sends_the_tap_role(self):
        with MonotonicPatch(self.remapper):
            self.assertTrue(self.remapper.down(CAPS))
            self.assertEqual(self.remapper.sent, [], "nothing is emitted until it resolves")

            self.remapper.clock += 0.05
            self.assertTrue(self.remapper.up(CAPS))

        self.assertEqual(self.remapper.sent, [(ESC, 'down'), (ESC, 'up')])

    def test_holding_and_pressing_another_key_sends_the_hold_role(self):
        with MonotonicPatch(self.remapper):
            self.remapper.down(CAPS)
            self.remapper.clock += 0.4

            self.assertFalse(self.remapper.down(KEY_J), "the other key passes through")
            self.assertEqual(self.remapper.sent, [(int(kr.VirtualKey.VK_CONTROL), 'down')])

            self.remapper.up(KEY_J)
            self.remapper.up(CAPS)

        self.assertEqual(self.remapper.sent[-1], (int(kr.VirtualKey.VK_CONTROL), 'up'))
        self.assertNotIn((ESC, 'down'), self.remapper.sent)

    def test_long_press_alone_sends_the_hold_role_once(self):
        with MonotonicPatch(self.remapper):
            self.remapper.down(CAPS)
            self.remapper.clock += 1.0
            self.remapper.up(CAPS)

        ctrl = int(kr.VirtualKey.VK_CONTROL)
        self.assertEqual(self.remapper.sent, [(ctrl, 'down'), (ctrl, 'up')])

    def test_auto_repeat_does_not_double_fire(self):
        with MonotonicPatch(self.remapper):
            self.remapper.down(CAPS)
            self.remapper.down(CAPS)
            self.remapper.down(CAPS)
            self.remapper.clock += 0.05
            self.remapper.up(CAPS)

        self.assertEqual(self.remapper.sent, [(ESC, 'down'), (ESC, 'up')])

    def test_hold_role_rejected_on_combinations(self):
        self.assertFalse(self.remapper.add_mapping('ctrl+j', 'a', hold='shift'))


class DefaultsTests(unittest.TestCase):

    def test_a_new_remapper_has_no_rules(self):
        """Nothing is blocked or remapped until the user says so."""
        remapper = FakeRemapper()
        self.assertEqual(remapper.list_mappings(), [])
        self.assertEqual(remapper.list_blocked_keys(), [])
        self.assertFalse(remapper.copilot.enabled)
        self.assertEqual(remapper.settings, kr.Settings())

    def test_slash_is_not_blocked_by_default(self):
        """Regression: '/' used to arrive pre-blocked from a stale dev config."""
        remapper = FakeRemapper()
        self.assertFalse(remapper.down(int(kr.VirtualKey.VK_OEM_2)))
        self.assertEqual(remapper.sent, [])

    def test_reset_clears_everything(self):
        remapper = FakeRemapper()
        remapper.add_mapping('capslock', 'escape', hold='ctrl')
        remapper.add_mapping('f1', 'a', app='game.exe')
        remapper.block_key('/')
        remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='keys', value='ralt'))
        remapper.apply_settings(kr.Settings(toggle_hotkey='ctrl+alt+f12', tap_timeout_ms=100))

        remapper.reset_to_defaults()

        self.assertEqual(remapper.list_mappings(), [])
        self.assertEqual(remapper.list_blocked_keys(), [])
        self.assertEqual(remapper.copilot, kr.CopilotConfig())
        self.assertEqual(remapper.settings, kr.Settings())
        self.assertIsNone(remapper._toggle_signature)
        self.assertFalse(remapper._has_app_rules)
        self.assertFalse(remapper._needs_mouse_hook)

    def test_keys_pass_through_after_a_reset(self):
        remapper = FakeRemapper()
        remapper.add_mapping('f13', 'a')
        remapper.block_key('f14')
        remapper.reset_to_defaults()

        self.assertFalse(remapper.down(F13))
        self.assertFalse(remapper.down(int(kr.VirtualKey.VK_F14)))
        self.assertEqual(remapper.sent, [])

    def test_reset_releases_a_key_that_is_still_held(self):
        remapper = FakeRemapper()
        remapper.add_mapping('f13', 'a')
        remapper.down(F13)
        remapper.reset_to_defaults()
        self.assertIn((KEY_A, 'up'), remapper.sent)

    def test_reset_is_persisted_as_an_empty_config(self):
        path = Path(tempfile.mkdtemp()) / "config.json"
        remapper = FakeRemapper()
        remapper.add_mapping('f13', 'a')
        remapper.save_config(path)

        remapper.reset_to_defaults()
        remapper.save_config(path)

        reloaded = FakeRemapper()
        reloaded.load_config(path)
        self.assertEqual(reloaded.list_mappings(), [])
        self.assertEqual(reloaded.settings, kr.Settings())

    def test_version_is_reported(self):
        self.assertRegex(kr.__version__, r'^\d+\.\d+\.\d+$')


class PauseTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()
        self.remapper.add_mapping('f13', 'a')
        self.remapper.apply_settings(kr.Settings(toggle_hotkey='ctrl+alt+f12'))

    def _press_hotkey(self):
        self.remapper.down(LCTRL)
        self.remapper.down(int(kr.VirtualKey.VK_LMENU))
        swallowed = self.remapper.down(int(kr.VirtualKey.VK_F12))
        self.remapper.up(int(kr.VirtualKey.VK_F12))
        self.remapper.up(int(kr.VirtualKey.VK_LMENU))
        self.remapper.up(LCTRL)
        return swallowed

    def test_hotkey_pauses_and_resumes(self):
        self.assertTrue(self._press_hotkey())
        self.assertTrue(self.remapper.paused)

        self.remapper.sent.clear()
        self.assertFalse(self.remapper.down(F13), "mappings are inert while paused")
        self.assertEqual(self.remapper.sent, [])

        self.assertTrue(self._press_hotkey())
        self.assertFalse(self.remapper.paused)
        self.assertTrue(self.remapper.down(F13))

    def test_pausing_releases_a_key_that_is_still_held(self):
        """Otherwise the injected target stays stuck down forever."""
        self.remapper.down(F13)
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

        self._press_hotkey()
        self.assertIn((KEY_A, 'up'), self.remapper.sent)

    def test_release_of_a_key_held_across_a_pause_is_still_swallowed(self):
        self.remapper.down(F13)
        self._press_hotkey()
        self.assertFalse(
            self.remapper.up(F13),
            "the source was released after the pause cleared it, so it passes through"
        )

    def test_toggle_hotkey_release_is_swallowed(self):
        self._press_hotkey()
        self.assertNotIn((int(kr.VirtualKey.VK_F12), 'down'), self.remapper.sent)

    def test_pause_callback_fires(self):
        seen = []
        self.remapper.on_pause_changed = seen.append
        self._press_hotkey()
        self.assertEqual(seen, [True])

    def test_invalid_hotkey_rejected(self):
        self.assertFalse(self.remapper.apply_settings(kr.Settings(toggle_hotkey='notakey')))


class CopilotTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()

    def _press_copilot(self):
        """What the firmware emits: Shift down, Win down, F23 down/up, releases."""
        self.remapper.down(LSHIFT)
        self.remapper.down(LWIN)
        swallowed = self.remapper.down(F23)
        self.remapper.up(F23)
        self.remapper.up(LWIN)
        self.remapper.up(LSHIFT)
        return swallowed

    def test_disable_mode_swallows_and_kills_the_start_menu(self):
        self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='disable'))
        self.assertTrue(self._press_copilot())
        self.assertEqual(
            self.remapper.sent,
            [(kr.DUMMY_KEY, 'down'), (kr.DUMMY_KEY, 'up')],
            "only the Start-menu neutraliser should be injected"
        )

    def test_keys_mode_releases_physical_modifiers_first(self):
        self.remapper.set_copilot(
            kr.CopilotConfig(enabled=True, mode='keys', value='ctrl+shift+p')
        )
        self._press_copilot()

        sent = self.remapper.sent
        self.assertEqual(sent[0], (kr.DUMMY_KEY, 'down'))
        self.assertIn((LWIN, 'up'), sent)
        self.assertIn((LSHIFT, 'up'), sent)
        self.assertLess(sent.index((LWIN, 'up')), sent.index((0x50, 'down')))
        self.assertEqual(sent[-1], (int(kr.VirtualKey.VK_SHIFT), 'up'))

    def test_modifier_target_is_held_until_the_key_is_released(self):
        """Copilot -> Right Alt should behave like the key it replaced."""
        self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='keys', value='ralt'))

        self.remapper.down(LSHIFT)
        self.remapper.down(LWIN)
        self.remapper.down(F23)
        self.assertIn((RALT, 'down'), self.remapper.sent)
        self.assertNotIn((RALT, 'up'), self.remapper.sent)

        self.remapper.up(F23)
        self.assertEqual(self.remapper.sent[-1], (RALT, 'up'))

    def test_menu_key_target_is_treated_as_a_modifier_style_target(self):
        self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='keys', value='apps'))
        self.remapper.down(LSHIFT)
        self.remapper.down(LWIN)
        self.remapper.down(F23)
        self.remapper.up(F23)
        self.assertIn((APPS, 'down'), self.remapper.sent)
        self.assertEqual(self.remapper.sent[-1], (APPS, 'up'))

    def test_non_modifier_target_is_a_one_shot_tap(self):
        self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='keys', value='f13'))
        self.remapper.down(LSHIFT)
        self.remapper.down(LWIN)
        self.remapper.down(F23)
        self.assertIn((F13, 'down'), self.remapper.sent)
        self.assertIn((F13, 'up'), self.remapper.sent)

    def test_passthrough_leaves_the_chord_alone(self):
        self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='passthrough'))
        self.assertFalse(self._press_copilot())
        self.assertEqual(self.remapper.sent, [])

    def test_wrong_chord_does_not_trigger(self):
        self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='disable'))
        self.remapper.down(LSHIFT)
        self.assertFalse(self.remapper.down(F23), "Win is missing, so this is not the chord")

    def test_invalid_target_keys_rejected(self):
        self.assertFalse(
            self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='keys', value='nope'))
        )

    def test_launch_mode_requires_a_value(self):
        self.assertFalse(
            self.remapper.set_copilot(kr.CopilotConfig(enabled=True, mode='launch', value='  '))
        )

    def test_chord_text_is_stable(self):
        config = kr.CopilotConfig(modifiers=('win', 'shift'), key=F23)
        self.assertEqual(config.chord_text(), 'SHIFT+WIN+F23')


class CaptureTests(unittest.TestCase):

    def setUp(self):
        self.remapper = FakeRemapper()
        self.captured = []
        self.remapper._capture_callback = self.captured.append

    def test_capture_reports_modifier_families_and_key(self):
        self.remapper.down(LSHIFT)
        self.remapper.down(LWIN)
        self.assertTrue(self.remapper.down(F23), "everything is swallowed while capturing")

        self.assertEqual(self.captured, [(('shift', 'win'), F23)])
        self.assertIsNone(self.remapper._capture_callback)

    def test_escape_cancels(self):
        self.remapper.down(ESC)
        self.assertEqual(self.captured, [None])

    def test_remaining_key_releases_are_drained(self):
        self.remapper.down(LWIN)
        self.remapper.down(F23)
        self.assertTrue(self.remapper.up(F23), "the tail of the chord must not leak")
        self.assertTrue(self.remapper.up(LWIN))
        self.assertFalse(self.remapper._capture_drain)


class ConfigTests(unittest.TestCase):

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "config.json"

    def test_round_trip_preserves_everything(self):
        original = FakeRemapper()
        original.add_mapping('capslock', 'escape', 'vim', hold='ctrl')
        original.add_mapping('f1', 'ctrl+s', app='notepad.exe')
        original.block_key('/', 'no chat', app='game.exe')
        original.set_copilot(kr.CopilotConfig(enabled=True, mode='keys', value='ralt'))
        original.apply_settings(kr.Settings(toggle_hotkey='ctrl+alt+f12', tap_timeout_ms=180))
        self.assertTrue(original.save_config(self.path))

        loaded = FakeRemapper()
        self.assertTrue(loaded.load_config(self.path))

        self.assertEqual(loaded.list_mappings(), original.list_mappings())
        self.assertEqual(loaded.list_blocked_keys(), original.list_blocked_keys())
        self.assertEqual(loaded.copilot, original.copilot)
        self.assertEqual(loaded.settings, original.settings)

    def test_every_field_of_every_feature_survives_a_save(self):
        """Guards against a new option being added to the engine but not the file."""
        original = FakeRemapper()
        original.add_mapping('capslock', 'escape', 'vim style', hold='ctrl')
        original.add_mapping('f1', 'ctrl+s', 'quick save', app=r'C:\Games\Game.EXE')
        original.add_mapping('mouse4', 'ctrl+c', 'copy button')
        original.add_mapping('ctrl+shift+a', 'f13', 'combo')
        original.add_mapping('f2', 'a', 'disabled one')
        original.toggle_mapping('f2')
        original.block_key('/', 'no chat', app='game.exe')
        original.block_key('win+d', 'no desktop')
        original.set_copilot(kr.CopilotConfig(
            enabled=True, modifiers=('ctrl',), key=F23,
            mode='launch', value=r'C:\Windows\notepad.exe', description='my copilot'
        ))
        original.apply_settings(kr.Settings(
            toggle_hotkey='ctrl+alt+f12', tap_timeout_ms=175,
            run_at_startup=True, start_minimized=True, start_on_launch=True,
        ))
        self.assertTrue(original.save_config(self.path))

        raw = json.loads(self.path.read_text(encoding='utf-8'))

        # Every mapping field is on disk
        capslock = next(m for m in raw['mappings'] if m['source'] == 'CAPS')
        self.assertEqual(capslock['hold'], 'CTRL')
        game = next(m for m in raw['mappings'] if m['app'])
        self.assertEqual(game['app'], 'game.exe', "app names are normalised before saving")
        mouse = next(m for m in raw['mappings'] if m['source'] == 'MOUSE4')
        self.assertEqual(mouse['target'], 'CTRL+C')
        self.assertFalse(next(m for m in raw['mappings'] if m['source'] == 'F2')['enabled'])

        # Blocked keys keep their scope
        self.assertEqual(
            {b['key']: b['app'] for b in raw['blocked_keys']},
            {'/': 'game.exe', 'LWIN+D': ''},
        )

        # Copilot and settings sections are complete
        self.assertEqual(raw['copilot'], {
            'enabled': True, 'modifiers': ['ctrl'], 'key': 'f23',
            'mode': 'launch', 'value': r'C:\Windows\notepad.exe',
            'description': 'my copilot',
        })
        self.assertEqual(raw['settings'], {
            'toggle_hotkey': 'ctrl+alt+f12', 'tap_timeout_ms': 175,
            'run_at_startup': True, 'start_minimized': True, 'start_on_launch': True,
        })

        # And it all comes back
        loaded = FakeRemapper()
        self.assertTrue(loaded.load_config(self.path))
        self.assertEqual(loaded.list_mappings(), original.list_mappings())
        self.assertEqual(loaded.list_blocked_keys(), original.list_blocked_keys())
        self.assertEqual(loaded.copilot, original.copilot)
        self.assertEqual(loaded.settings, original.settings)
        self.assertEqual(loaded._toggle_signature, original._toggle_signature)
        self.assertEqual(loaded._needs_mouse_hook, original._needs_mouse_hook)
        self.assertEqual(loaded._has_app_rules, original._has_app_rules)

    def test_saved_dataclass_fields_are_all_serialised(self):
        """If someone adds a field to Settings, this fails until save_config knows."""
        import dataclasses
        remapper = FakeRemapper()
        remapper.save_config(self.path)
        raw = json.loads(self.path.read_text(encoding='utf-8'))

        self.assertEqual(
            set(raw['settings']),
            {f.name for f in dataclasses.fields(kr.Settings)},
        )
        self.assertEqual(
            set(raw['copilot']),
            {f.name for f in dataclasses.fields(kr.CopilotConfig)},
        )
        mapping_fields = {f.name for f in dataclasses.fields(kr.KeyMapping)}
        saved_mapping_keys = {'source', 'target', 'hold', 'app', 'enabled', 'description'}
        self.assertEqual(
            mapping_fields - {'source_keys', 'target_keys', 'hold_keys'},
            saved_mapping_keys - {'source', 'target', 'hold'},
        )

    def test_disabled_rules_stay_disabled(self):
        original = FakeRemapper()
        original.add_mapping('f13', 'a')
        original.toggle_mapping('f13')
        original.save_config(self.path)

        loaded = FakeRemapper()
        loaded.load_config(self.path)
        self.assertFalse(loaded.list_mappings()[0]['enabled'])

    def test_missing_file_is_not_an_error(self):
        self.assertFalse(FakeRemapper().load_config(self.path / "nope.json"))

    def test_corrupt_file_is_handled(self):
        self.path.write_text("{ not json", encoding='utf-8')
        self.assertFalse(FakeRemapper().load_config(self.path))

    def test_v2_config_without_new_sections_still_loads(self):
        self.path.write_text(json.dumps({
            "mappings": [{"source": "CAPSLOCK", "target": "ESCAPE", "enabled": True}],
            "blocked_keys": [{"key": "/", "enabled": True}],
        }), encoding='utf-8')

        loaded = FakeRemapper()
        self.assertTrue(loaded.load_config(self.path))
        self.assertEqual(len(loaded.list_mappings()), 1)
        self.assertFalse(loaded.copilot.enabled)
        self.assertEqual(loaded.settings, kr.Settings())

    def test_settings_tap_timeout_is_clamped(self):
        self.assertEqual(kr.settings_from_dict({"tap_timeout_ms": 99999}).tap_timeout_ms, 2000)
        self.assertEqual(kr.settings_from_dict({"tap_timeout_ms": "junk"}).tap_timeout_ms, 250)

    def test_copilot_key_accepts_name_or_code(self):
        self.assertEqual(kr.copilot_from_dict({"key": "f23"}).key, F23)
        self.assertEqual(kr.copilot_from_dict({"key": F23}).key, F23)
        self.assertEqual(kr.copilot_from_dict({"key": None}).key, kr.DEFAULT_COPILOT_KEY)


if __name__ == '__main__':
    unittest.main(verbosity=2)
