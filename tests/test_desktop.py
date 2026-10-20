from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import desktop


class DesktopTests(unittest.TestCase):
    def window(self, root):
        with patch.object(desktop, 'BrowserJob'), patch.object(desktop.setup_webview, 'ready', return_value=True), patch.object(desktop.subprocess, 'Popen') as popen:
            process = popen.return_value
            process.poll.return_value = None
            window = desktop.AppWindow('http://127.0.0.1:1234/?t=test', root)
            args = popen.call_args.args[0]
            self.assertTrue(args[0].endswith('Rune.exe'))
            self.assertEqual(args[2], str(window.profile))
            self.assertEqual(window.profile.parent, Path(root) / 'webview2-data')
            self.assertFalse(any(k.upper().startswith('WEBVIEW2_') for k in popen.call_args.kwargs['env']))
            return window, process

    def test_host_exit_stops_server(self):
        with tempfile.TemporaryDirectory() as root:
            window, process = self.window(root)
            process.poll.return_value = 0
            close = Mock()
            window.watch(close)
            close.assert_called_once()
            self.assertIsNone(window.error)
            window.close()
            window.job.close.assert_called_once()
            self.assertFalse(window.profile.exists())

    def test_failed_host_exit_stops_server(self):
        with tempfile.TemporaryDirectory() as root:
            window, process = self.window(root)
            process.poll.return_value = 1
            close = Mock()
            window.watch(close)
            close.assert_called_once()
            self.assertIn('exited unexpectedly', window.error)
            window.close()

    def test_quit_requests_graceful_host_close(self):
        with tempfile.TemporaryDirectory() as root:
            window, process = self.window(root)
            process.poll.side_effect = [None, 0]
            window.close()
            process.stdin.write.assert_called_once_with('close\n')
            process.terminate.assert_not_called()
            close = Mock()
            window.watch(close)
            close.assert_not_called()

    def test_launch_failure_removes_session_data(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(desktop, 'BrowserJob'), patch.object(desktop.setup_webview, 'ready', return_value=True), patch.object(desktop.subprocess, 'Popen', side_effect=OSError('failed')):
                with self.assertRaises(OSError):
                    desktop.AppWindow('url', root)
            self.assertEqual(list((Path(root)/'webview2-data').iterdir()), [])

    def test_missing_host_does_not_launch(self):
        with patch.object(desktop.setup_webview, 'ready', return_value=False), patch.object(desktop.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(RuntimeError, 'Launch Rune'):
                desktop.AppWindow('url', Path('.'))
            popen.assert_not_called()
