"""Windows dialog ABI and results without opening an interactive dialog."""
import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import platforms
import launch


@unittest.skipUnless(os.name == 'nt', 'Windows common dialog API')
class WindowsPickerTests(unittest.TestCase):
    def call(self, selected=None, error=0):
        api = Mock()
        def show(pointer):
            options = pointer._obj
            self.assertEqual(options.lStructSize, 152 if ctypes.sizeof(ctypes.c_void_p) == 8 else 88)
            self.assertEqual(options.nMaxFile, 32768)
            self.assertTrue(options.Flags & 8, 'Dialog must not change the server cwd')
            self.assertTrue(options.Flags & 0x1000, 'Selected file must exist')
            self.assertEqual(options.lpstrInitialDir, str(Path.home()))
            if selected is not None:
                # Read the pointer itself; LPWSTR fields otherwise convert to Python strings.
                address = ctypes.c_void_p.from_address(ctypes.addressof(options) + type(options).lpstrFile.offset).value
                value = ctypes.create_unicode_buffer(selected)
                ctypes.memmove(address, value, ctypes.sizeof(value))
                return True
            return False
        api.GetOpenFileNameW.side_effect = show
        api.CommDlgExtendedError.return_value = error
        with patch.object(ctypes, 'WinDLL', return_value=api):
            return platforms._windows_file_picker(Path.home())

    def test_unicode_selection(self):
        path = 'C:\\Users\\Test\\Viking æ א\\my character.fch'
        self.assertEqual(self.call(path), path)

    def test_cancel(self):
        self.assertIsNone(self.call())

    def test_error_is_not_cancel(self):
        with self.assertRaisesRegex(ValueError, '0x3003'):
            self.call(error=0x3003)

    def test_windows_dispatch_does_not_import_tk(self):
        with patch.object(platforms, 'MACOS', False), patch.object(platforms, 'WINDOWS', True), patch.object(platforms, '_windows_file_picker', return_value='a.fch') as picker:
            self.assertEqual(platforms.pick_character_file(), 'a.fch')
            picker.assert_called_once()


class LauncherTests(unittest.TestCase):
    def test_check_does_not_start_server(self):
        with patch.object(sys, 'argv', ['launch.py', '--check']), patch.object(launch, 'check_runtime'), patch.object(launch.runpy, 'run_path') as run:
            self.assertEqual(launch.main(), 0)
            run.assert_not_called()

    def test_old_python_is_rejected(self):
        with patch.object(sys, 'version_info', (3, 8)):
            with self.assertRaisesRegex(RuntimeError, 'minimum compatible'):
                launch.check_runtime()


if __name__ == '__main__':
    unittest.main()
