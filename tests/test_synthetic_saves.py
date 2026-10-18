"""Character open/save on synthetic saves, so CI covers the write path without private fixtures."""
import io,json,os,sys,tempfile,unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from subscripts.fchUtil import compile_fch
from subscripts.playerDataUtil import pack_player_data_hex

def synthetic_fch(player_version):
    item=dict(prefab='Wood',prefab_hash=0,stack=5,quality=1,durability=100.0,grid_x=0,grid_y=0,world_level=0,variant=0,
              equipped=False,picked_up=True,crafter_id=0,crafter_name='',custom_data={},cheated=False)
    player=dict(version=player_version,inventory=[item],foods=[],pseudo_counters=[],item_upgrade_seeds=[])
    root=dict(version={33:46,34:47}[player_version],stat_count=1,profile_count=1,profiles=[dict(stats=[0.0],enemy_stats=[{}]*5)],
              character_name='Synthetic',player_id=123456789,start_seed='seed',player_data_hex=pack_player_data_hex(player),worlds=[])
    with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder,redirect_stdout(io.StringIO()):
        wrapper=Path(folder)/'wrapper.json';out=Path(folder)/'out.fch'
        wrapper.write_text(json.dumps(root));compile_fch(str(wrapper),str(out))
        return out.read_bytes()

class SyntheticSaveTests(unittest.TestCase):
    def setUp(self):
        check=patch.object(server,'ensure_game_closed');check.start();self.addCleanup(check.stop)
        self.temp=tempfile.TemporaryDirectory(dir=server.RUNTIME);self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'viking.fch'

    def leftovers(self):
        return [p.name for p in self.path.parent.iterdir() if p.suffix=='.tmp']

    def test_both_formats_open_and_export_unchanged(self):
        for version,versions in ((33,[46,33,109]),(34,[47,34,110])):
            with self.subTest(version=version):
                raw=synthetic_fch(version);data=server.open_save(raw,'viking.fch')
                self.assertEqual(data['versions'],versions)
                self.assertEqual(server.export_save(data),raw)

    def test_save_replaces_file_and_keeps_verified_backup(self):
        raw=synthetic_fch(34);self.path.write_bytes(raw)
        data=server.open_local_path(self.path);data['player']['health']=17.0
        result=server.save_character(data)
        self.assertFalse(result['unchanged'])
        self.assertEqual(Path(result['backup']).read_bytes(),raw)
        self.assertEqual(server.decode(self.path.read_bytes())[1]['health'],17.0)
        self.assertEqual(self.leftovers(),[])

    def test_failed_install_leaves_original_and_backup(self):
        raw=synthetic_fch(34);self.path.write_bytes(raw)
        data=server.open_local_path(self.path);data['player']['health']=17.0
        with patch.object(server,'install_staged',side_effect=OSError('disk full')),self.assertRaises(OSError):server.save_character(data)
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual([p.read_bytes() for p in (self.path.parent/'.rune-backups').iterdir()],[raw])
        self.assertEqual(self.leftovers(),[])

    def test_browse_opens_the_literal_picked_file(self):
        picked=Path(self.temp.name)/'$RUNE_TEST_VAR.fch';picked.write_bytes(synthetic_fch(34))
        (Path(self.temp.name)/'other.fch').write_bytes(synthetic_fch(33))
        with patch.dict(os.environ,{'RUNE_TEST_VAR':'other'}),patch.object(server,'pick_character_file',return_value=str(picked)):
            self.assertEqual(server.browse_character()['sourcePath'],str(picked.resolve()))

class CatalogueIconTests(unittest.TestCase):
    def test_missing_icons_keep_variant_positions(self):
        entry=next(e for e in server.CATALOG if len(e['icons'])>1)
        names=json.loads((server.EDITOR/'local-data/valheim_items.json').read_text(encoding='utf-8'))['items'][str(entry['hash'])]['icons']
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/names[1]).write_bytes(b'')
            with patch.object(server,'ICONS',Path(folder)):icons=next(e for e in server.catalogue() if e['hash']==entry['hash'])['icons']
        self.assertEqual(icons[:2],[None,names[1]])

if __name__=='__main__':unittest.main()
