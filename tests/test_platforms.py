"""Platform layer: save discovery, game-process checks and the file picker, without Steam or Valheim installed."""
import subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import platforms

def ps(stdout,code=0):
    return subprocess.CompletedProcess(['/bin/ps'],code,stdout=stdout,stderr='')

class ProcessTests(unittest.TestCase):
    def test_cloud_guard_detects_steam_processes(self):
        for name in ('steam.exe', 'steamwebhelper.exe', 'Steam', 'steam_osx'):
            with self.subTest(name=name),patch.object(platforms,'WINDOWS',True),patch.object(platforms,'_windows_processes',return_value=[name]):
                with self.assertRaisesRegex(ValueError,'Exit Steam'):platforms.ensure_steam_closed()
        with patch.object(platforms,'WINDOWS',True),patch.object(platforms,'_windows_processes',return_value=['explorer.exe']):
            platforms.ensure_steam_closed()

    def check_macos(self,result):
        with patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',True),patch.object(platforms.subprocess,'run',return_value=result):
            platforms.ensure_game_closed()

    def test_running_mac_game_blocks_save(self):
        with self.assertRaisesRegex(ValueError,'Close Valheim'):
            self.check_macos(ps('/sbin/launchd\n/Users/x/Library/Application Support/Steam/steamapps/common/Valheim/Valheim.app/Contents/MacOS/Valheim\n/bin/ps\n'))

    def test_dedicated_server_and_wine_builds_block_save(self):
        for name in ('valheim_server.x86_64','valheim.exe'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Close Valheim'):
                self.check_macos(ps(f'/sbin/launchd\n/opt/{name}\n'))

    def test_closed_game_allows_save(self):
        self.check_macos(ps('/sbin/launchd\n/Applications/Safari.app/Contents/MacOS/Safari\n/bin/ps\n'))

    def test_failed_or_empty_process_list_fails_closed(self):
        for result in (ps('',0),ps('/sbin/launchd\n/bin/ps\n',1)):
            with self.subTest(code=result.returncode),self.assertRaisesRegex(ValueError,'Save cancelled'):
                self.check_macos(result)
        with patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',True),patch.object(platforms.subprocess,'run',side_effect=OSError):
            with self.assertRaisesRegex(ValueError,'Save cancelled'):platforms.ensure_game_closed()

    def test_unsupported_platform_refuses_direct_save(self):
        with patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',False):
            with self.assertRaisesRegex(ValueError,'only enabled'):platforms.ensure_game_closed()

    @unittest.skipUnless(sys.platform=='darwin','needs the real macOS ps')
    def test_real_ps_runs(self):
        self.assertGreater(len(platforms._macos_processes()),1)
        platforms.ensure_game_closed()

    @unittest.skipUnless(sys.platform=='win32','needs the real Windows process snapshot')
    def test_real_windows_snapshot_runs(self):
        self.assertGreater(len(platforms._windows_processes()),1)
        platforms.ensure_game_closed()

class DiscoveryTests(unittest.TestCase):
    def test_steam_cloud_dirs_found_for_any_account(self):
        with tempfile.TemporaryDirectory() as folder:
            for account in ('111','222'):(Path(folder)/f'userdata/{account}/892970/remote/characters').mkdir(parents=True)
            (Path(folder)/'userdata/333/12345/remote/characters').mkdir(parents=True)
            with patch.dict(platforms.os.environ,{'RUNE_STEAM_DIR':folder}),patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',False):
                found=platforms.steam_remote_dirs('characters')
            self.assertEqual([p.parts[-4] for p in found],['111','222'])

    def test_macos_locations(self):
        with patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',True),patch.dict(platforms.os.environ,{},clear=False):
            platforms.os.environ.pop('RUNE_STEAM_DIR',None)
            self.assertEqual(platforms.local_dirs('worlds'),[Path.home()/'Library/Application Support/IronGate/Valheim/worlds_local'])
            self.assertEqual(platforms.steam_roots(),[Path.home()/'Library/Application Support/Steam'])

    def test_mac_steam_cache_is_read_only(self):
        import server
        self.assertTrue(server.is_cloud_cache(Path.home()/'Library/Application Support/Steam/userdata/42/892970/remote/characters/a.fch'))
        self.assertFalse(server.is_cloud_cache(Path.home()/'Library/Application Support/IronGate/Valheim/characters_local/a.fch'))

class PickerTests(unittest.TestCase):
    def pick(self,result):
        with patch.object(platforms,'MACOS',True),patch.object(platforms.subprocess,'run',return_value=result) as run:
            return platforms.pick_character_file(),run.call_args[0][0]

    def test_mac_picker_returns_path_and_passes_folder_as_argument(self):
        path,args=self.pick(subprocess.CompletedProcess([],0,stdout='/Users/x/a.fch\n',stderr=''))
        self.assertEqual(path,'/Users/x/a.fch')
        self.assertEqual(args[0],'/usr/bin/osascript')
        self.assertNotIn(args[-1],' '.join(args[:-1]))

    def test_mac_picker_cancel(self):
        path,_=self.pick(subprocess.CompletedProcess([],1,stdout='',stderr='execution error: User canceled. (-128)'))
        self.assertIsNone(path)

    def test_mac_picker_failure_is_reported(self):
        with self.assertRaisesRegex(ValueError,'file picker'):
            self.pick(subprocess.CompletedProcess([],1,stdout='',stderr='execution error: boom (-1743)'))

class NameAndFlushTests(unittest.TestCase):
    def test_ps_fallback_forms_still_match(self):
        for entry in ('(Valheim)','(valheim_server)','-Valheim','C:\\Games\\Valheim\\valheim.exe','/Applications/Valheim.app/Contents/MacOS/Valheim'):
            with self.subTest(entry=entry):self.assertTrue(platforms.is_game_process(entry))
        for entry in ('(bash)','-zsh','/Applications/Safari.app/Contents/MacOS/Safari'):
            with self.subTest(entry=entry):self.assertFalse(platforms.is_game_process(entry))

    def test_parenthesised_game_blocks_save_and_names_it(self):
        with patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',True),patch.object(platforms.subprocess,'run',return_value=ps('/sbin/launchd\n(Valheim)\n/bin/ps\n')):
            with self.assertRaisesRegex(ValueError,'"Valheim"'):platforms.ensure_game_closed()

    def flush_with(self,error):
        import fcntl
        with tempfile.TemporaryFile() as stream,patch.object(platforms,'MACOS',True),patch.object(fcntl,'fcntl',side_effect=error),patch.object(platforms.os,'fsync') as fsync:
            platforms.flush_to_disk(stream)
            return fsync.call_count

    @unittest.skipUnless(sys.platform=='darwin','F_FULLFSYNC exists only on macOS')
    def test_unsupported_full_fsync_falls_back_to_fsync(self):
        import errno
        for code in (errno.ENOTSUP,errno.EINVAL):
            with self.subTest(code=code):self.assertEqual(self.flush_with(OSError(code,'unsupported')),1)

    @unittest.skipUnless(sys.platform=='darwin','F_FULLFSYNC exists only on macOS')
    def test_real_io_error_still_fails_the_save(self):
        import errno
        with self.assertRaises(OSError):self.flush_with(OSError(errno.EIO,'I/O error'))

    def test_steam_dir_override_expands_home(self):
        with patch.dict(platforms.os.environ,{'RUNE_STEAM_DIR':'~/SteamX'}),patch.object(platforms,'WINDOWS',False),patch.object(platforms,'MACOS',False):
            self.assertEqual(platforms.steam_roots(),[Path.home()/'SteamX'])

class PickerErrorTests(unittest.TestCase):
    def test_error_mentioning_128_elsewhere_is_not_a_cancel(self):
        result=subprocess.CompletedProcess([],1,stdout='',stderr="execution error: Can't get /Users/x/test-128/a. (-1700)")
        with patch.object(platforms,'MACOS',True),patch.object(platforms.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(ValueError,'file picker'):platforms.pick_character_file()

if __name__=='__main__':unittest.main()
