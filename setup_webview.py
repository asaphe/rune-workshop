"""Build Rune's small Windows host from source using the official WebView2 SDK."""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parent
VERSION = '1.0.4258.31'
SHA256 = '56f7f4b8bf9aee4b8efefbbdd4f67d5f74ebd1b100ed0806da71bf76af481aa9'
URL = ('https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/' + VERSION +
       '/microsoft.web.webview2.' + VERSION + '.nupkg')


def architecture():
    # The Framework host runs x64 under emulation on Windows ARM64.
    machine = os.environ.get('PROCESSOR_ARCHITEW6432') or platform.machine()
    return 'x86' if machine.lower() in ('x86', 'i386', 'i686') else 'x64'


def target():
    digest = hashlib.sha256((BASE / 'native/RuneHost.cs').read_bytes() +
                            (BASE / 'web/rune.ico').read_bytes() +
                            (VERSION + architecture()).encode()).hexdigest()[:16]
    return BASE / '.runtime' / ('webview-host-' + digest)


def ready():
    folder = target()
    return all((folder / name).is_file() for name in (
        'Rune.exe', 'Microsoft.Web.WebView2.Core.dll',
        'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll', 'ready.json'))


def extract_sdk(raw, folder, arch):
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('WebView2 SDK checksum mismatch.')
    names = {
        'lib/net462/Microsoft.Web.WebView2.Core.dll': 'Microsoft.Web.WebView2.Core.dll',
        'lib/net462/Microsoft.Web.WebView2.WinForms.dll': 'Microsoft.Web.WebView2.WinForms.dll',
        'build/native/' + arch + '/WebView2Loader.dll': 'WebView2Loader.dll',
        'LICENSE.txt': 'WebView2-LICENSE.txt',
    }
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member, name in names.items():
            (folder / name).write_bytes(archive.read(member))


def build():
    if ready():
        return target() / 'Rune.exe'
    arch = architecture()
    compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET' / (
        'Framework64' if arch == 'x64' else 'Framework') / 'v4.0.30319/csc.exe'
    if not compiler.is_file():
        raise RuntimeError('Rune needs Windows .NET Framework 4.6.2 or newer.')
    runtime = BASE / '.runtime'
    runtime.mkdir(exist_ok=True)
    print('Downloading Microsoft WebView2 SDK from NuGet...', flush=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        raw = response.read()
    with tempfile.TemporaryDirectory(prefix='webview-build-', dir=runtime) as temp:
        folder = Path(temp)
        extract_sdk(raw, folder, arch)
        args = [str(compiler), '/nologo', '/target:winexe', '/platform:' + arch,
                '/out:' + str(folder / 'Rune.exe'), '/win32icon:' + str(BASE / 'web/rune.ico'),
                '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
                '/reference:' + str(folder / 'Microsoft.Web.WebView2.Core.dll'),
                '/reference:' + str(folder / 'Microsoft.Web.WebView2.WinForms.dll'),
                str(BASE / 'native/RuneHost.cs')]
        subprocess.run(args, check=True)
        (folder / 'ready.json').write_text(json.dumps({'sdk': VERSION, 'sha256': SHA256}))
        # A complete versioned directory is published only once compilation succeeds.
        destination = target()
        if destination.exists():
            raise RuntimeError('Incomplete host folder: remove ' + str(destination) + ' and retry setup.')
        folder.rename(destination)
    return destination / 'Rune.exe'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        raise SystemExit(0 if ready() else 1)
    host = build()
    if subprocess.run([str(host), '--check']).returncode:
        raise SystemExit('Install Microsoft Edge WebView2 Evergreen Runtime, then launch Rune again: '
                         'https://developer.microsoft.com/microsoft-edge/webview2/')
    print('Rune WebView2 host is ready.')
