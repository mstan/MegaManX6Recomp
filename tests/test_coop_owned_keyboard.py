"""Owned key delivery must preserve message flags, ownership and key release."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_owned_keyboard as subject


class OwnedKeyboardTests(unittest.TestCase):
    def test_win32_message_flags_are_exact_and_keys_bounded(self):
        self.assertEqual(subject.key_lparam(0x41,'F7',False),0x00410001)
        self.assertEqual(subject.key_lparam(0x41,'F7',True),0xc0410001)
        self.assertEqual(subject.key_lparam(0x4b,'Left',False),0x014b0001)
        for scan,key in ((0,'F7'),(256,'F7'),(True,'F7'),(0x41,'Alt')):
            with self.assertRaises(ValueError):subject.key_lparam(scan,key,False)

    def test_message_is_not_posted_after_window_pid_changes(self):
        keys=subject.OwnedKeyboard.__new__(subject.OwnedKeyboard)
        keys.ctx={'request':Mock()};keys.evidence={'keyboard_events':[]};keys.pid=123;keys.window={'hwnd':45}
        keys.api=Mock();keys.api.MapVirtualKeyW.return_value=0x41;keys.api.PostMessageW.return_value=True
        def owner(hwnd,out):out._obj.value=124
        keys.api.GetWindowThreadProcessId.side_effect=owner
        with self.assertRaises(ValueError):keys.post('F7',False)
        keys.api.PostMessageW.assert_not_called()
        def correct_owner(hwnd,out):out._obj.value=123
        keys.api.GetWindowThreadProcessId.side_effect=correct_owner
        keys.post('F7',False)
        keys.api.PostMessageW.assert_called_once_with(45,0x100,0x76,0x00410001)
        self.assertTrue(keys.evidence['keyboard_events'][0]['posted'])

    def test_observer_error_still_releases_the_same_owned_key(self):
        keys=subject.OwnedKeyboard.__new__(subject.OwnedKeyboard);keys.post=Mock()
        def wait(*args):raise RuntimeError('native UI did not acknowledge')
        with self.assertRaisesRegex(RuntimeError,'native UI'):
            keys.until('F8',lambda:False,wait,'F8')
        self.assertEqual([c.args for c in keys.post.call_args_list],[('F8',False),('F8',True)])

    def test_lost_ownership_during_release_does_not_hide_the_original_error(self):
        keys=subject.OwnedKeyboard.__new__(subject.OwnedKeyboard);keys.evidence={}
        keys.post=Mock(side_effect=[None,RuntimeError('listener no longer owned')])
        def wait(*args):raise ValueError('original native busy response')
        with self.assertRaisesRegex(ValueError,'original native busy'):
            keys.until('F7',lambda:False,wait,'F7')
        self.assertEqual(keys.evidence['keyboard_release_errors'],
                         [dict(key='F7',error='listener no longer owned')])


if __name__=='__main__':unittest.main()
