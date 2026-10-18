"""Integration checks against private fixture copies (never modify Steam files)."""
import copy
import os
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

FIXTURES = Path(os.environ.get('RUNE_FIXTURES') or Path(__file__).resolve().parents[3] / 'work/fixtures')

@unittest.skipUnless((FIXTURES / 'current-v47.fch').exists(), 'private save fixtures not available; set RUNE_FIXTURES')
class SaveTests(unittest.TestCase):
    def setUp(self):
        self.process_check=patch.object(server,'ensure_game_closed')
        self.process_check.start()
        self.addCleanup(self.process_check.stop)

    def opened(self, name='current-v47.fch'):
        raw = (FIXTURES / name).read_bytes()
        return raw, server.open_save(raw, name)

    def test_all_supplied_formats_unchanged(self):
        for name in ('current-v47.fch', 'backup-v46.fch', 'other-v46.fch'):
            with self.subTest(name=name):
                raw, data = self.opened(name)
                self.assertEqual(server.export_save(data), raw)

    def test_edits_preserve_every_other_field(self):
        raw, data = self.opened()
        before_root, expected = server.decode(raw)
        data['player']['health'] = expected['health'] = 50.0
        data['player']['foods'][0]['time'] = expected['foods'][0]['time'] = 600.0
        data['player']['inventory'][0]['quality'] = expected['inventory'][0]['quality'] = 3
        result = server.export_save(data)
        root, player = server.decode(result)
        self.assertEqual(player, expected)
        root.pop('player_data_hex'); before_root.pop('player_data_hex')
        self.assertEqual(root, before_root)
        self.assertEqual(server.SESSIONS[data['session']][2], raw)

    def test_death_timer_edit_preserves_other_data(self):
        raw, data = self.opened()
        root, expected = server.decode(raw)
        self.assertEqual(data['player']['time_since_death'], expected['time_since_death'])
        data['player']['time_since_death'] = expected['time_since_death'] = 29 * 1800
        result = server.export_save(data)
        after, player = server.decode(result)
        self.assertEqual(player, expected)
        after.pop('player_data_hex'); root.pop('player_data_hex')
        self.assertEqual(after, root)
        for invalid in (-1, float('nan'), float('inf'), True, '52200', 10000001):
            data['player']['time_since_death'] = invalid
            with self.assertRaises(ValueError): server.export_save(data)

    def test_large_crafter_id_survives_browser_json(self):
        _, data = self.opened()
        data['player']['inventory'][0]['crafter_id'] = '9223372036854775806'
        _, player = server.decode(server.export_save(data))
        self.assertEqual(player['inventory'][0]['crafter_id'], 9223372036854775806)

    def test_character_and_item_cheat_flags(self):
        raw, data = self.opened()
        root, player = server.decode(raw)
        data['usedCheats'] = True
        data['player']['inventory'][0]['cheated'] = True
        marked = server.export_save(data)
        flagged_root, flagged_player = server.decode(marked)
        self.assertTrue(flagged_root['used_cheats'])
        self.assertTrue(flagged_player['inventory'][0]['cheated'])
        reopened = server.open_save(marked, 'marked.fch')
        reopened['usedCheats'] = False
        for item in reopened['player']['inventory']: item['cheated'] = False
        cleared_root, cleared_player = server.decode(server.export_save(reopened))
        root['used_cheats'] = False
        for item in player['inventory']: item['cheated'] = False
        self.assertEqual(cleared_player, player)
        root.pop('player_data_hex'); cleared_root.pop('player_data_hex')
        self.assertEqual(cleared_root, root)

    def test_reject_invalid_edits(self):
        _, data = self.opened()
        for key, value in [('health', float('nan')), ('health', -1), ('model_index', 2)]:
            attempt = copy.deepcopy(data); attempt['player'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                server.export_save(attempt)
        attempt = copy.deepcopy(data)
        attempt['player']['inventory'].append(copy.deepcopy(attempt['player']['inventory'][0]))
        with self.assertRaises(ValueError): server.export_save(attempt)

    def test_replaced_foods_persist_to_file_and_preserve_backup(self):
        raw,_=self.opened()
        with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
            path=Path(folder)/'food-test.fch';path.write_bytes(raw)
            data=server.open_save(raw,path.name,path)
            foods=[dict(name=n,time=server.FOOD_DATA['foods'][n]['duration']) for n in ('Eyescream','FishAndBread','DeerStew')]
            data['player']['foods']=foods
            result=server.save_character(data)
            self.assertEqual(server.decode(path.read_bytes())[1]['foods'],foods)
            self.assertEqual(Path(result['backup']).read_bytes(),raw)
            self.assertEqual(server.open_save(path.read_bytes(),path.name)['player']['foods'],foods)
            for invalid in ([dict(name='Wood',time=100)], [foods[0],foods[0]], [dict(name='Eyescream',time=1e7)]):
                data['player']['foods']=invalid
                with self.assertRaises(ValueError):server.export_save(data)

    def test_corrupt_input_rejected(self):
        raw, _ = self.opened()
        damaged = bytearray(raw); damaged[-1] ^= 1
        with self.assertRaises(ValueError): server.open_save(bytes(damaged), 'broken.fch')

    def test_save_retains_original_and_supports_repeated_saves(self):
        raw, _ = self.opened()
        with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
            path=Path(folder)/'viking.fch';path.write_bytes(raw)
            data=server.open_save(raw,path.name,path)
            data['player']['health']=50
            result=server.save_character(data)
            first=path.read_bytes()
            self.assertEqual(Path(result['backup']).read_bytes(),raw)
            self.assertTrue(result['backup'].endswith('.fch.old'))
            self.assertEqual(server.decode(first)[1]['health'],50)
            data['player']['health']=60
            second=server.save_character(data)
            self.assertNotEqual(second['backup'],result['backup'])
            self.assertEqual(Path(second['backup']).read_bytes(),first)
            self.assertEqual(server.decode(path.read_bytes())[1]['health'],60)
            self.assertTrue(server.save_character(data)['unchanged'])
            self.assertEqual(len(list(Path(folder).rglob('*.old'))),2)

    def test_save_rejects_external_change_and_upload_without_path(self):
        raw,data=self.opened()
        with self.assertRaises(ValueError):server.save_character(data)
        with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
            path=Path(folder)/'viking.fch';path.write_bytes(raw)
            data=server.open_save(raw,path.name,path)
            path.write_bytes(b'newer save')
            with self.assertRaises(ValueError):server.save_character(data)
            self.assertEqual(path.read_bytes(),b'newer save')
            self.assertEqual(len(list(Path(folder).rglob('*.old'))),0)

    def test_save_restores_original_if_install_fails(self):
        raw,_=self.opened()
        with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
            path=Path(folder)/'viking.fch';path.write_bytes(raw)
            data=server.open_save(raw,path.name,path);data['player']['health']=50
            with patch.object(server,'install_staged',side_effect=OSError('simulated failure')):
                with self.assertRaises(OSError):server.save_character(data)
            self.assertEqual(path.read_bytes(),raw)
            self.assertEqual(len(list(Path(folder).rglob('*.old'))),1)
            self.assertEqual(next(Path(folder).rglob('*.old')).read_bytes(),raw)

    def test_cloud_cache_write_blocked(self):
        raw,_=self.opened()
        with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
            path=Path(folder)/'userdata/12345678/892970/remote/characters/test.fch'
            path.parent.mkdir(parents=True);path.write_bytes(raw)
            data=server.open_save(raw,path.name,path)
            self.assertFalse(data['canSave'])
            data['player']['health']=50
            with self.assertRaisesRegex(ValueError,'Steam Cloud'):server.save_character(data)
            self.assertEqual(path.read_bytes(),raw)

    def test_running_game_blocks_save(self):
        raw,_=self.opened()
        with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
            path=Path(folder)/'test.fch';path.write_bytes(raw)
            data=server.open_save(raw,path.name,path)
            with patch.object(server,'ensure_game_closed',side_effect=ValueError('Close Valheim')):
                with self.assertRaisesRegex(ValueError,'Close Valheim'):server.save_character(data)
            self.assertEqual(path.read_bytes(),raw)

    def test_truncated_file_is_rejected(self):
        raw,_=self.opened()
        with self.assertRaises((EOFError,ValueError)):server.open_save(raw[:-135],'truncated.fch')

if __name__ == '__main__': unittest.main()


