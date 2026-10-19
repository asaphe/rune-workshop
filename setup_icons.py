"""Optional, local-only artwork setup. Normal Rune startup needs no packages."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))  # Official embeddable Python leaves the script dir out.
from platforms import steam_roots

UNITY_VERSION = '1.24.2'
PIP_VERSION = '26.2.1'


def bundles_path(game):
    return Path(game) / 'valheim_Data/StreamingAssets/SoftRef/Bundles'


def discover_games(roots=None):
    libraries = list(steam_roots() if roots is None else roots)
    if roots is None and os.name == 'nt':
        libraries.extend(Path(f'{drive}:/{name}') for drive in 'CDEFGHIJKLMNOPQRSTUVWXYZ'
                         for name in ('Steam', 'SteamLibrary'))
    for root in list(libraries):
        try:
            vdf = (root / 'steamapps/libraryfolders.vdf').read_text(encoding='utf-8')
            libraries.extend(Path(s.replace('\\\\', '\\')) for s in re.findall(r'"path"\s+"([^"]+)"', vdf))
        except OSError:
            continue
    return list(dict.fromkeys(str(root / 'steamapps/common/Valheim') for root in libraries
                             if bundles_path(root / 'steamapps/common/Valheim').is_dir()))


def download(url):
    if not url.startswith(('https://pypi.org/', 'https://files.pythonhosted.org/')):
        raise ValueError('Unexpected package download host.')
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def install_tools(destination):
    """Use a verified pip wheel temporarily; never install pip into Python itself."""
    metadata = json.loads(download(f'https://pypi.org/pypi/pip/{PIP_VERSION}/json'))
    wheel = next(f for f in metadata['urls'] if f['filename'].endswith('py3-none-any.whl'))
    payload = download(wheel['url'])
    if hashlib.sha256(payload).hexdigest() != wheel['digests']['sha256']:
        raise ValueError('pip download checksum mismatch.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        wheel_path = Path(folder) / wheel['filename']
        wheel_path.write_bytes(payload)
        # Explicit sys.path also works with an unchanged embeddable ._pth file.
        bootstrap = 'import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module("pip",run_name="__main__")'
        environment = dict(os.environ, TEMP=folder, TMP=folder)
        subprocess.run([sys.executable, '-E', '-s', '-c', bootstrap, str(wheel_path),
                        '--isolated', 'install', '--disable-pip-version-check', '--no-cache-dir',
                        '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
                        '--target', str(destination), f'UnityPy=={UNITY_VERSION}'], check=True, env=environment)


def write_icon(image, folder):
    output = io.BytesIO()
    image.convert('RGBA').save(output, format='PNG')
    data = output.getvalue()
    name = hashlib.sha256(data).hexdigest() + '.png'
    (folder / name).write_bytes(data)
    return name


def extract(game, destination, unity):
    """Read ItemDrop sprites; publish only after at least one icon was decoded."""
    bundles = bundles_path(game)
    if not bundles.is_dir():
        raise ValueError('Choose the Valheim folder containing valheim_Data, not a save folder.')
    env = unity.Environment()
    files = sorted(p for p in bundles.iterdir() if p.is_file())
    if not files:
        raise ValueError('No Valheim bundles found in this folder.')
    for index, file in enumerate(files, 1):
        print(f'Loading game artwork {index}/{len(files)}', flush=True)
        env.load_file(str(file))
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        stage = Path(temporary)
        icons = {}
        failures = 0
        cache = {}
        for obj in env.objects:
            if obj.type.name != 'GameObject':
                continue
            try:
                prefab = obj.peek_name()
                components = obj.read().m_Component
            except Exception:
                continue
            for entry in components:
                try:
                    component = entry.component.deref()
                    if component is None or component.type.name != 'MonoBehaviour':
                        continue
                    mono = component.read()
                    script = mono.m_Script.deref()
                    if script is None or script.read().m_ClassName != 'ItemDrop':
                        continue
                    references = mono.m_itemData.m_shared.m_icons
                except Exception:
                    continue
                names = []
                for reference in references or []:
                    try:
                        sprite = reference.deref()
                        if sprite is None:
                            names.append(None)
                            continue
                        key = (id(sprite.assets_file), sprite.path_id)
                        if key not in cache:
                            cache[key] = write_icon(sprite.read().image, stage)
                        names.append(cache[key])
                    except Exception:
                        failures += 1
                        names.append(None)
                if any(names):
                    icons[prefab] = names
                break
        if not icons:
            raise RuntimeError('No item pictures could be decoded. Existing artwork was preserved.')
        index_path = destination / 'item-icons.json'
        previous = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
        previous.update(icons)
        output = destination / 'item_icons'
        output.mkdir(exist_ok=True)
        for png in stage.glob('*.png'):
            png.replace(output / png.name)
        (stage / 'index.json').write_text(json.dumps(previous), encoding='utf-8')
        (stage / 'index.json').replace(index_path)
        print(f'Item pictures ready: {len(icons)} items; {failures} unreadable sprites use placeholders.', flush=True)
        return len(icons)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--detect', action='store_true')
    parser.add_argument('--game', type=Path)
    parser.add_argument('--tools', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.detect:
        print(json.dumps(discover_games()))
        return
    if args.game is None or not bundles_path(args.game).is_dir():
        raise ValueError('Choose the Valheim installation containing valheim_Data.')
    if args.tools:
        sys.path.insert(0, str(args.tools))
        import UnityPy
        extract(args.game, BASE / 'backend/local-data', UnityPy)
        return
    # Each setup gets a clean tool folder, so an interrupted package download
    # cannot poison a retry. These dependencies never enter the server's path.
    runtime = BASE / '.runtime'
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='icon-tools-', dir=runtime) as folder:
        tools = Path(folder) / 'packages'
        print('Downloading optional artwork tools from PyPI...', flush=True)
        install_tools(tools)
        # The child releases loaded Windows DLLs before the parent removes tools.
        subprocess.run([sys.executable, '-E', '-s', str(Path(__file__).resolve()),
                        '--game', str(args.game), '--tools', str(tools)], check=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Icon setup failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
