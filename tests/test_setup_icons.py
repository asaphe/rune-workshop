import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch

import setup_icons as setup


class IconSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_detects_additional_steam_library_and_deduplicates(self):
        steam = self.root / 'Steam'
        library = self.root / 'Other library'
        (steam / 'steamapps').mkdir(parents=True)
        (steam / 'steamapps/libraryfolders.vdf').write_text(
            '"libraryfolders" { "1" { "path" "' + str(library).replace('\\', '\\\\') + '" } }')
        game = library / 'steamapps/common/Valheim'
        setup.bundles_path(game).mkdir(parents=True)
        self.assertEqual(setup.discover_games([steam, library]), [str(game)])

    def test_invalid_game_fails_before_downloading_dependencies(self):
        with patch('sys.argv', ['setup_icons.py', '--game', str(self.root)]), patch.object(setup, 'install_tools') as install:
            with self.assertRaises(ValueError):
                setup.main()
            install.assert_not_called()

    def test_rejects_wrong_pip_hash_before_execution(self):
        metadata = {'urls': [{'filename': 'pip-py3-none-any.whl', 'url': 'https://files.pythonhosted.org/pip.whl',
                              'digests': {'sha256': '0' * 64}}]}
        with patch.object(setup, 'download', side_effect=[json.dumps(metadata).encode(), b'bad']), patch.object(setup.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                setup.install_tools(self.root / 'tools')
            run.assert_not_called()

    def environment(self, readable=True):
        class Image:
            def convert(self, mode): return self
            def save(self, output, format): output.write(b'fake-png-for-unit-test')
        sprite = NS(assets_file=object(), path_id=1, read=lambda: NS(image=Image()))
        references = [NS(deref=lambda: None), NS(deref=lambda: sprite if readable else None)]
        mono = NS(m_Script=NS(deref=lambda: NS(read=lambda: NS(m_ClassName='ItemDrop'))),
                  m_itemData=NS(m_shared=NS(m_icons=references)))
        component = NS(type=NS(name='MonoBehaviour'), read=lambda: mono)
        obj = NS(type=NS(name='GameObject'), peek_name=lambda: 'Wood',
                 read=lambda: NS(m_Component=[NS(component=NS(deref=lambda: component))]))
        return NS(Environment=lambda: NS(load_file=lambda p: None, objects=[obj]))

    def game(self):
        folder = self.root / 'game'
        setup.bundles_path(folder).mkdir(parents=True)
        (setup.bundles_path(folder) / 'bundle').write_bytes(b'fake')
        return folder

    def test_extract_preserves_variant_slots_and_other_metadata(self):
        output = self.root / 'local-data'
        output.mkdir()
        (output / 'item-icons.json').write_text('{"Other":["existing.png"]}')
        self.assertEqual(setup.extract(self.game(), output, self.environment()), 1)
        index = json.loads((output / 'item-icons.json').read_text())
        name = hashlib.sha256(b'fake-png-for-unit-test').hexdigest() + '.png'
        self.assertEqual(index, {'Other': ['existing.png'], 'Wood': [None, name]})
        self.assertEqual((output / 'item_icons' / name).read_bytes(), b'fake-png-for-unit-test')

    def test_failed_extraction_preserves_old_index(self):
        output = self.root / 'local-data'
        output.mkdir()
        old = b'{"Wood":["existing.png"]}'
        (output / 'item-icons.json').write_bytes(old)
        with self.assertRaisesRegex(RuntimeError, 'No item pictures'):
            setup.extract(self.game(), output, self.environment(False))
        self.assertEqual((output / 'item-icons.json').read_bytes(), old)


if __name__ == '__main__':
    unittest.main()
