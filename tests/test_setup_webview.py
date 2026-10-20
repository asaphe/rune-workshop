import io
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import setup_webview as setup


class WebViewSetupTests(unittest.TestCase):
    def test_rejects_bad_hash_before_extracting(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                setup.extract_sdk(b'bad package', Path(root), 'x64')
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_extracts_only_required_members(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name in ('lib/net462/Microsoft.Web.WebView2.Core.dll',
                         'lib/net462/Microsoft.Web.WebView2.WinForms.dll',
                         'build/native/x64/WebView2Loader.dll', 'LICENSE.txt', '../escape.txt'):
                archive.writestr(name, name)
        raw = stream.getvalue()
        with tempfile.TemporaryDirectory() as root, patch.object(setup, 'SHA256', hashlib.sha256(raw).hexdigest()):
            setup.extract_sdk(raw, Path(root), 'x64')
            self.assertEqual({p.name for p in Path(root).iterdir()},
                             {'Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll',
                              'WebView2Loader.dll', 'WebView2-LICENSE.txt'})

    def test_ready_requires_complete_host(self):
        with tempfile.TemporaryDirectory() as root, patch.object(setup, 'target', return_value=Path(root)):
            (Path(root) / 'Rune.exe').touch()
            self.assertFalse(setup.ready())
            for name in ('Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll',
                         'WebView2Loader.dll', 'ready.json'):
                (Path(root) / name).touch()
            self.assertTrue(setup.ready())
