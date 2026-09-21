"""
Tests for the key remapper engine.

These drive ``_handle_key_event`` directly instead of installing a real hook, so
the whole rule engine - remaps, blocks, dual-role keys, per-app profiles, the
pause hotkey and the Copilot key - is testable without touching the keyboard.

Run with:  python -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import threading
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
    """A remapper that records injected keys and actions instead of running them."""

    def __init__(self):
        super().__init__()
        self.sent = []
        self.actions = []
        self.typed = []
        self.clock = 1000.0

    def _send_key(self, vk_code, key_up=False):
        self.sent.append((vk_code, 'up' if key_up else 'down'))

    def _queue_action(self, action, value):
        self.actions.append((action, value))

    def _send_text(self, text):
        self.typed.append(text)

    def now(self):
        return self.clock

    def down(self, vk, scan=0):
        return self._handle_key_event(vk, True, False, scan)

    def up(self, vk, scan=0):
        return self._handle_key_event(vk, False, True, scan)

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

        self.assertEqual(
            self.captured,
            [kr.CapturedChord(modifiers=('shift', 'win'), vk=F23, scan_code=0)]
        )
        self.assertIsNone(self.remapper._capture_callback)

    def test_capture_records_the_scan_code(self):
        self.remapper.down(F23, scan=0x6E)
        self.assertEqual(self.captured[0].scan_code, 0x6E)
        self.assertEqual(self.captured[0].hardware_text(), 'vk 0x86 \u00b7 scan 0x6E')

    def test_capture_of_an_unnamed_key_is_still_mappable(self):
        self.remapper.down(0x97)  # a code with no friendly name
        chord = self.captured[0]
        self.assertFalse(chord.is_named_key())
        self.assertEqual(chord.key_string(), 'vk0x97')
        self.assertEqual(
            FakeRemapper().parse_key_string(chord.key_string()), (0x97,)
        )

    def test_escape_cancels(self):
        self.remapper.down(ESC)
        self.assertEqual(self.captured, [None])

    def test_remaining_key_releases_are_drained(self):
        self.remapper.down(LWIN)
        self.remapper.down(F23)
        self.assertTrue(self.remapper.up(F23), "the tail of the chord must not leak")
        self.assertTrue(self.remapper.up(LWIN))
        self.assertFalse(self.remapper._capture_drain)


class RawKeyCodeTests(unittest.TestCase):
    """Keyboards send keys we have no name for - especially under Fn."""

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_hex_code_is_parsed(self):
        self.assertEqual(self.remapper.parse_key_string('vk0x5d'), (0x5D,))

    def test_decimal_code_is_parsed(self):
        self.assertEqual(self.remapper.parse_key_string('vk93'), (93,))

    def test_code_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            self.remapper.parse_key_string('vk0x1FF')

    def test_unnamed_code_round_trips_through_a_rule(self):
        self.assertTrue(self.remapper.add_mapping('vk0x97', 'a'))
        self.assertEqual(self.remapper.list_mappings()[0]['source'], 'VK0X97')
        self.assertTrue(self.remapper.down(0x97))
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

    def test_named_keys_still_win(self):
        self.assertEqual(kr.vk_name(F23), 'f23')


class FnKeyNotSupportedTests(unittest.TestCase):
    """
    Fn is deliberately not a modifier.

    Nearly every keyboard handles Fn in its own controller and never tells
    Windows, so an "fn" that parsed but never matched would be a trap. These
    guard against it creeping back in.
    """

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_fn_is_not_a_key_name(self):
        with self.assertRaises(ValueError):
            self.remapper.parse_key_string('fn')

    def test_fn_combination_is_rejected_outright(self):
        with self.assertRaises(ValueError):
            self.remapper.parse_key_string('fn+f12')

    def test_a_rule_using_fn_cannot_be_added(self):
        self.assertFalse(self.remapper.add_mapping('fn+f12', 'mute'))
        self.assertEqual(self.remapper.list_mappings(), [])

    def test_no_fn_modifier_family(self):
        self.assertNotIn('fn', kr.MODIFIER_FAMILY.values())
        self.assertNotIn('fn', kr.FAMILY_GENERIC_VK)

    def test_the_limitation_is_documented_in_the_code(self):
        notice = kr.FN_KEY_NOTICE.lower()
        self.assertIn('fn', notice)
        self.assertIn('combination', notice)

    def test_settings_no_longer_carry_a_learned_fn_code(self):
        fields = {f.name for f in __import__('dataclasses').fields(kr.Settings)}
        self.assertNotIn('fn_vk', fields)
        self.assertNotIn('fn_scan', fields)

    def test_an_old_config_with_fn_fields_still_loads(self):
        """Anyone who ran the build that had Fn detection must not be stranded."""
        path = Path(tempfile.mkdtemp()) / "old.json"
        path.write_text(json.dumps({
            "version": 5,
            "mappings": [{"source": "F13", "target": "A", "enabled": True}],
            "settings": {"tap_timeout_ms": 200, "fn_vk": 255, "fn_scan": 93},
        }), encoding='utf-8')

        loaded = FakeRemapper()
        self.assertTrue(loaded.load_config(path))
        self.assertEqual(loaded.settings.tap_timeout_ms, 200)
        self.assertEqual(len(loaded.list_mappings()), 1)

    def test_an_old_config_with_an_fn_rule_skips_just_that_rule(self):
        path = Path(tempfile.mkdtemp()) / "oldrule.json"
        path.write_text(json.dumps({
            "version": 5,
            "mappings": [
                {"source": "FN+F12", "target": "", "action": "launch",
                 "value": "calc.exe", "enabled": True},
                {"source": "F13", "target": "A", "enabled": True},
            ],
        }), encoding='utf-8')

        loaded = FakeRemapper()
        self.assertTrue(loaded.load_config(path), "one bad rule must not fail the load")
        sources = [m['source'] for m in loaded.list_mappings()]
        self.assertEqual(sources, ['F13'])


class TypeTextTests(unittest.TestCase):
    """
    "text" rules type characters rather than keys, so the keyboard layout
    cannot change what comes out - the reason the action exists.
    """

    RCTRL = int(kr.VirtualKey.VK_RCONTROL)

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_key_types_its_text_and_is_swallowed(self):
        self.assertTrue(self.remapper.add_mapping('f13', '', action='text', value='.'))
        self.assertTrue(self.remapper.down(F13))
        self.assertEqual(self.remapper.typed, ['.'])
        self.assertEqual(self.remapper.sent, [], "no virtual key is sent at all")
        self.assertTrue(self.remapper.up(F13), "the release is swallowed too")

    def test_the_period_and_comma_setup_from_the_bug_report(self):
        """rctrl types '.', shift+rctrl types ',' - whatever the layout."""
        self.remapper.add_mapping('rctrl', '', action='text', value='.')
        self.remapper.add_mapping('shift+rctrl', '', action='text', value=',')

        self.remapper.down(self.RCTRL)
        self.remapper.up(self.RCTRL)
        self.remapper.down(LSHIFT)
        self.remapper.down(self.RCTRL)

        self.assertEqual(self.remapper.typed, ['.', ','])

    def test_holding_the_key_repeats_the_text(self):
        self.remapper.add_mapping('f13', '', action='text', value='.')
        for _ in range(3):
            self.remapper.down(F13)   # auto-repeat delivers repeated key-downs
        self.assertEqual(self.remapper.typed, ['.', '.', '.'])

    def test_whitespace_is_kept(self):
        self.remapper.add_mapping('f13', '', action='text', value=', ')
        self.remapper.down(F13)
        self.assertEqual(self.remapper.typed, [', '])

    def test_a_lone_space_is_valid_text(self):
        self.assertTrue(self.remapper.add_mapping('f13', '', action='text', value=' '))

    def test_empty_text_is_rejected(self):
        self.assertFalse(self.remapper.add_mapping('f13', '', action='text', value=''))

    def test_text_expansion(self):
        self.remapper.add_mapping('ctrl+alt+m', '', action='text', value='me@example.com')
        self.remapper.down(LCTRL)
        self.remapper.down(int(kr.VirtualKey.VK_LMENU))
        self.remapper.down(0x4D)
        self.assertEqual(self.remapper.typed, ['me@example.com'])

    def test_hold_roles_do_not_mix_with_text(self):
        self.assertFalse(self.remapper.add_mapping(
            'capslock', '', hold='ctrl', action='text', value='.'))

    # --- the Settings switch ----------------------------------------------

    def test_switching_typing_off_lets_the_key_through(self):
        self.remapper.add_mapping('f13', '', action='text', value='.')
        self.remapper.apply_settings(kr.Settings(type_text_enabled=False))

        self.assertFalse(self.remapper.down(F13), "the physical key does its normal job")
        self.assertEqual(self.remapper.typed, [])
        self.assertEqual(len(self.remapper.list_mappings()), 1, "the rule is kept, not deleted")

    def test_switching_typing_back_on_restores_it(self):
        self.remapper.add_mapping('f13', '', action='text', value='.')
        self.remapper.apply_settings(kr.Settings(type_text_enabled=False))
        self.remapper.down(F13)
        self.remapper.up(F13)

        self.remapper.apply_settings(kr.Settings(type_text_enabled=True))
        self.assertTrue(self.remapper.down(F13))
        self.assertEqual(self.remapper.typed, ['.'])

    def test_the_switch_leaves_other_rules_alone(self):
        self.remapper.add_mapping('f13', '', action='text', value='.')
        self.remapper.add_mapping('f14', 'a')
        self.remapper.apply_settings(kr.Settings(type_text_enabled=False))

        self.assertTrue(self.remapper.down(int(kr.VirtualKey.VK_F14)))
        self.assertEqual(self.remapper.sent, [(KEY_A, 'down')])

    def test_the_switch_does_not_disable_blocks(self):
        self.remapper.block_key('f13')
        self.remapper.apply_settings(kr.Settings(type_text_enabled=False))
        self.assertTrue(self.remapper.down(F13))

    def test_switch_defaults_on_and_survives_a_save(self):
        self.assertTrue(kr.Settings().type_text_enabled)
        path = Path(tempfile.mkdtemp()) / "text.json"
        self.remapper.apply_settings(kr.Settings(type_text_enabled=False))
        self.remapper.save_config(path)

        loaded = FakeRemapper()
        loaded.load_config(path)
        self.assertFalse(loaded.settings.type_text_enabled)

    def test_older_configs_have_typing_on(self):
        self.assertTrue(kr.settings_from_dict({"tap_timeout_ms": 200}).type_text_enabled)

    # --- persistence and display -----------------------------------------

    def test_text_rule_round_trips_exactly(self):
        path = Path(tempfile.mkdtemp()) / "rules.json"
        self.remapper.add_mapping('f13', '', action='text', value=', ')
        self.remapper.add_mapping('f14', '', action='text', value='ю — €')
        self.remapper.save_config(path)

        loaded = FakeRemapper()
        loaded.load_config(path)
        self.assertEqual(loaded.list_mappings(), self.remapper.list_mappings())
        values = [m['value'] for m in loaded.list_mappings()]
        self.assertEqual(values, [', ', 'ю — €'])

    def test_listed_target_shows_the_text(self):
        self.remapper.add_mapping('f13', '', action='text', value='.')
        self.assertEqual(self.remapper.list_mappings()[0]['display_target'], '✎ “.”')

    def test_test_button_types_immediately(self):
        self.remapper.run_action('text', 'hi')
        self.assertEqual(self.remapper.typed, ['hi'])


class UnicodeInjectionTests(unittest.TestCase):
    """The real _send_text, with SendInput captured instead of called."""

    def setUp(self):
        self.calls = []
        self.original = kr.user32.SendInput

        def capture(count, events, size):
            self.calls.append([
                (events[i].union.ki.wVk, events[i].union.ki.wScan,
                 events[i].union.ki.dwFlags, events[i].union.ki.dwExtraInfo)
                for i in range(count)
            ])
            return count

        kr.user32.SendInput = capture
        self.addCleanup(self._restore)
        self.remapper = kr.KeyRemapper()

    def _restore(self):
        kr.user32.SendInput = self.original

    def test_each_character_is_a_unicode_down_up_pair(self):
        self.remapper._send_text('.,')
        marker = self.remapper._injection_marker
        self.assertEqual(self.calls, [[
            (0, ord('.'), kr.KEYEVENTF_UNICODE, marker),
            (0, ord('.'), kr.KEYEVENTF_UNICODE | kr.KEYEVENTF_KEYUP, marker),
            (0, ord(','), kr.KEYEVENTF_UNICODE, marker),
            (0, ord(','), kr.KEYEVENTF_UNICODE | kr.KEYEVENTF_KEYUP, marker),
        ]])

    def test_no_virtual_key_is_involved(self):
        """wVk = 0 is what makes the result immune to the keyboard layout."""
        self.remapper._send_text('ю.')
        self.assertTrue(all(event[0] == 0 for event in self.calls[0]))

    def test_whole_text_goes_in_one_call(self):
        """One SendInput call, so other input cannot interleave with it."""
        self.remapper._send_text('hello world')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0]), 22)

    def test_emoji_is_sent_as_a_surrogate_pair(self):
        self.remapper._send_text('😀')
        units = [event[1] for event in self.calls[0] if not event[2] & kr.KEYEVENTF_KEYUP]
        self.assertEqual(units, [0xD83D, 0xDE00])

    def test_injected_text_is_tagged_as_ours(self):
        """The hook must skip its own packets or a rule could trigger itself."""
        self.remapper._send_text('.')
        self.assertTrue(all(e[3] == self.remapper._injection_marker for e in self.calls[0]))

    def test_empty_text_sends_nothing(self):
        self.remapper._send_text('')
        self.assertEqual(self.calls, [])


class MappingActionTests(unittest.TestCase):
    """A key can open an app or a website instead of sending keys."""

    def setUp(self):
        self.remapper = FakeRemapper()

    def test_launch_mapping_runs_the_action_and_swallows_the_key(self):
        self.assertTrue(self.remapper.add_mapping(
            'f13', '', action='launch', value='calc.exe'))

        self.assertTrue(self.remapper.down(F13))
        self.assertEqual(self.remapper.actions, [('launch', 'calc.exe')])
        self.assertEqual(self.remapper.sent, [], "nothing is typed")
        self.assertTrue(self.remapper.up(F13), "the release is swallowed too")

    def test_url_mapping(self):
        self.remapper.add_mapping('f13', '', action='url', value='claude.ai')
        self.remapper.down(F13)
        self.assertEqual(self.remapper.actions, [('url', 'claude.ai')])

    def test_launch_needs_a_value(self):
        self.assertFalse(self.remapper.add_mapping('f13', '', action='launch'))

    def test_unknown_action_rejected(self):
        self.assertFalse(self.remapper.add_mapping(
            'f13', '', action='detonate', value='x'))

    def test_hold_roles_do_not_mix_with_launching(self):
        self.assertFalse(self.remapper.add_mapping(
            'capslock', '', hold='ctrl', action='launch', value='calc.exe'))

    def test_held_windows_key_does_not_open_the_start_menu(self):
        self.remapper.add_mapping('win+f13', '', action='launch', value='calc.exe')
        self.remapper.down(LWIN)
        self.remapper.sent.clear()

        self.assertTrue(self.remapper.down(F13))
        self.assertIn((kr.DUMMY_KEY, 'down'), self.remapper.sent)
        self.assertIn((LWIN, 'up'), self.remapper.sent,
                      "the held Win key is released before the app opens")

    def test_disabled_launch_mapping_does_nothing(self):
        self.remapper.add_mapping('f13', '', action='launch', value='calc.exe')
        self.remapper.toggle_mapping('f13')
        self.assertFalse(self.remapper.down(F13))
        self.assertEqual(self.remapper.actions, [])

    def test_per_app_scope_applies_to_actions(self):
        self.remapper.add_mapping('f13', '', app='game.exe',
                                  action='launch', value='calc.exe')
        foreground = ['notepad.exe']
        self.remapper._foreground_exe = lambda: foreground[0]

        self.assertFalse(self.remapper.down(F13))
        self.assertEqual(self.remapper.actions, [])

        foreground[0] = 'game.exe'
        self.assertTrue(self.remapper.down(F13))
        self.assertEqual(self.remapper.actions, [('launch', 'calc.exe')])

    def test_listed_target_describes_the_action(self):
        self.remapper.add_mapping('f13', '', action='launch', value='calc.exe')
        self.remapper.add_mapping('f14', '', action='url', value='claude.ai')
        targets = [m['display_target'] for m in self.remapper.list_mappings()]
        self.assertEqual(targets, ['\u25b6 calc.exe', '\U0001f310 claude.ai'])

    def test_conflict_message_names_the_app(self):
        self.remapper.add_mapping('f13', '', action='launch', value='calc.exe')
        self.assertIn('calc.exe', self.remapper.find_conflict('f13'))

    def test_action_survives_a_config_round_trip(self):
        path = Path(tempfile.mkdtemp()) / "actions.json"
        self.remapper.add_mapping('f13', '', 'open the calculator',
                                  action='launch', value='calc.exe')
        self.remapper.add_mapping('f14', '', action='url', value='claude.ai')
        self.remapper.save_config(path)

        loaded = FakeRemapper()
        self.assertTrue(loaded.load_config(path))
        self.assertEqual(loaded.list_mappings(), self.remapper.list_mappings())

    def test_protocol_uri_is_opened_by_the_shell(self):
        """Packaged apps have no .exe, so they must not go through the shell."""
        self.assertTrue(kr.KeyRemapper._URI_SCHEME.match('ms-settings:'))
        self.assertTrue(kr.KeyRemapper._URI_SCHEME.match('shell:AppsFolder\\x'))
        self.assertIsNone(kr.KeyRemapper._URI_SCHEME.match(r'C:\Windows\calc.exe'))
        self.assertIsNone(kr.KeyRemapper._URI_SCHEME.match('calc.exe'))

    def test_shipped_app_presets_are_usable(self):
        for name, command in kr.COMMON_APPS:
            self.assertTrue(name and command, name)

    def test_shipped_target_presets_all_parse(self):
        for group, items in kr.COMMON_TARGETS:
            for label, value in items:
                with self.subTest(group=group, label=label):
                    self.remapper.parse_key_string(value)


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
            'type_text_enabled': True,
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
        saved_mapping_keys = {'source', 'target', 'action', 'value', 'hold', 'app',
                              'enabled', 'description'}
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


class SingleInstanceTests(unittest.TestCase):
    """Only one copy may run - a second one hands over instead of hooking too."""

    def setUp(self):
        # A private namespace, so these never collide with a copy of the app
        # the developer happens to have running on this machine
        self.scope = f"KeyRemapperTest_{os.getpid()}_{id(self)}"
        self.owner = self.instance()
        self.addCleanup(self.owner.release)

    def instance(self) -> kr.SingleInstance:
        made = kr.SingleInstance(scope=self.scope)
        self.addCleanup(made.release)
        return made

    def test_first_copy_wins(self):
        self.assertTrue(self.owner.acquire())

    def test_second_copy_is_turned_away(self):
        self.owner.acquire()
        self.assertFalse(self.instance().acquire())

    def test_second_copy_wakes_the_first(self):
        self.owner.acquire()
        woken = threading.Event()
        self.owner.listen(woken.set)

        other = self.instance()
        other.acquire()
        self.assertTrue(other.signal_existing())
        self.assertTrue(woken.wait(timeout=5.0), "the running copy must be told")

    def test_the_signal_can_fire_more_than_once(self):
        """The event auto-resets, so every later launch reopens the window."""
        self.owner.acquire()
        count = []
        ready = threading.Event()

        def woken():
            count.append(1)
            ready.set()

        self.owner.listen(woken)
        for _ in range(3):
            ready.clear()
            other = self.instance()
            other.acquire()
            other.signal_existing()
            self.assertTrue(ready.wait(timeout=5.0))
            other.release()
        self.assertEqual(len(count), 3)

    def test_a_rejected_copy_does_not_keep_the_mutex_alive(self):
        self.owner.acquire()
        rejected = self.instance()
        rejected.acquire()
        rejected.release()

        self.owner.release()
        self.assertTrue(self.instance().acquire(),
                        "once the owner exits, the next launch takes over")

    def test_signalling_nobody_is_not_an_error(self):
        self.owner.acquire()
        self.assertFalse(self.owner.signal_existing())

    def test_release_is_safe_to_repeat(self):
        self.owner.acquire()
        self.owner.release()
        self.owner.release()


if __name__ == '__main__':
    unittest.main(verbosity=2)
