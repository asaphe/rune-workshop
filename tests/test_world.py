"""Synthetic world fixtures: no user saves are needed or modified."""
import copy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import world

class WorldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=server.RUNTIME)
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.item=dict(prefab='Wood',prefab_hash=world.hashcode('Wood'),stack=10,quality=1,durability=100,grid_x=0,grid_y=0,world_level=0,variant=0,crafter_id='9223372036854775806',crafter_name='Viking',custom_data={'mod':'preserve'},cheated=True,_cheat_byte=129)
        inv=world.encode_inventory(110,[self.item],[])
        def obj(creator):
            return world.p('Hfffi',0xa0,1.,2.,3.,world.hashcode('piece_chest_wood'))+bytes([1])+world.p('iq',world.hashcode('creator'),creator)+bytes([1])+world.p('ii',world.hashcode('items'),len(inv))+inv
        chunk=world.p('hi',42,2)+obj(123)+obj(0)
        (self.path/'00_01__0_1.chunk').write_bytes(chunk)
        (self.path/'_main.1.chunks').write_bytes(world.p('hiiHBIi',42,2,1,1,0,1,2))
        (self.path/'_main.1.db2').write_bytes(b'opaque world metadata')
        meta=world.p('i',42)+world.string('Test world')+world.string('seed')+world.p('iqiB',1,123,1,1)+world.p('i',1)+world.string('eventrate 60')+world.p('i',0)
        (self.path/'_main.1.fwl2').write_bytes(world.p('i',len(meta))+meta)
        (self.path/'_main.1.ok').write_bytes(world.p('i',42))
        self.w=world.World(self.path)
    def changes(self):
        items=copy.deepcopy(self.w.containers[0]['items']);items[0]['stack']=11
        return [dict(id='0',items=items)]
    def test_player_filter_and_noop(self):
        self.assertEqual(len(self.w.containers),1)
        self.assertEqual(self.w.containers[0]['creator'],'123')
        self.assertIsNone(self.w.build([dict(id='0',items=self.w.containers[0]['items'])]))
    def test_patch_preserves_other_object_and_opaque_item_fields(self):
        original=self.w.files['00_01__0_1.chunk'];c=self.w.containers[0]
        _,files=self.w.build(self.changes());raw=next(v for k,v in files.items() if k.endswith('.chunk'))
        self.assertEqual(raw[:c['start']],original[:c['start']])
        self.assertEqual(raw[c['end']+len(raw)-len(original):],original[c['end']:])
        _,containers=world.parse_chunk(raw);i=containers[0]['items'][0]
        self.assertEqual(i['stack'],11)
        self.assertEqual(i['crafter_id'],'9223372036854775806')
        self.assertEqual(i['custom_data'],{'mod':'preserve'})
        self.assertEqual(i['_cheat_byte'],129)
    def test_failed_write_never_commits_and_retry_succeeds(self):
        real=world.durable;before=sorted(p.name for p in self.path.iterdir())
        def fail(path,data,created=None):
            if path.suffix=='.fwl2':raise OSError('injected failure')
            real(path,data,created)
        with patch.object(world,'durable',side_effect=fail):
            with self.assertRaises(OSError):self.w.save(self.changes(),lambda:None)
        self.assertEqual(sorted(p.name for p in self.path.iterdir() if p.name!='.rune-backups'),before)
        self.assertEqual(world.World(self.path).number,1)
        self.assertTrue(list((self.path/'.rune-backups').glob('*.zip')))
        result=self.w.save(self.changes(),lambda:None)
        self.assertGreater(result['generation'],1)
        self.assertEqual(self.w.containers[0]['items'][0]['stack'],11)
    def test_duplicate_stack_preserves_item_metadata(self):
        original=self.w.containers[0]['items'][0]
        items=copy.deepcopy(self.w.containers[0]['items'])
        duplicate=copy.deepcopy(original);duplicate['grid_x']=1;duplicate['stack']=50
        items.append(duplicate)
        _,files=self.w.build([dict(id='0',items=items)])
        raw=next(v for k,v in files.items() if k.endswith('.chunk'))
        _,containers=world.parse_chunk(raw)
        result=containers[0]['items']
        self.assertEqual(len(result),2)
        self.assertEqual(result[0],original)
        for key in ('custom_data','crafter_id','crafter_name','_cheat_byte','quality','durability'):
            self.assertEqual(result[1][key],original[key])
        self.assertEqual((result[1]['grid_x'],result[1]['stack']),(1,50))
        self.assertEqual(self.w.containers[0]['items'],[original])

    def test_external_changes_rejected(self):
        (self.path/'00_01__0_1.chunk').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.w.save(self.changes(),lambda:None)
    def test_generated_container_cannot_be_targeted(self):
        with self.assertRaises(ValueError):self.w.build([dict(id='1',items=[])])
    def test_settings_toggle_and_restore_preserve_metadata(self):
        raw=self.w.files['_main.1.fwl2']
        number,files=self.w.build([],settings={'nobuildcost':True})
        edited=files[f'_main.{number}.fwl2']
        self.assertEqual(world.metadata(edited)['keys'],['eventrate 60','nobuildcost'])
        self.assertEqual(world.patch_settings(edited,{'nobuildcost':False}),raw)
        self.assertIsNone(self.w.build([],settings={'nobuildcost':False}))
        with self.assertRaises(ValueError):self.w.build([],settings={'nocraftcost':True})
        with self.assertRaises(ValueError):self.w.build([],settings={'nobuildcost':'yes'})
        self.w.save([],lambda:None,settings={'nobuildcost':True})
        self.assertTrue(self.w.public()['settings']['nobuildcost'])
        self.w.save([],lambda:None,settings={'nobuildcost':False})
        self.assertFalse(self.w.public()['settings']['nobuildcost'])
    def test_combat_and_frequency_preserve_unrelated_settings(self):
        raw=self.w.files['_main.1.fwl2']
        self.assertEqual(world.world_settings(world.metadata(raw)['keys'])['raidFrequency'],'more')
        self.assertEqual(world.patch_settings(raw,world.world_settings(world.metadata(raw)['keys'])),raw)
        edited=world.patch_settings(raw,{'combatDifficulty':'hard'})
        keys=world.metadata(edited)['keys']
        self.assertIn('eventrate 60',keys)
        self.assertIn('enemydamage 150',keys)
        self.assertEqual(world.world_settings(keys)['combatDifficulty'],'hard')
        self.assertEqual(world.patch_settings(edited,{'combatDifficulty':'normal'}),raw)
        custom=edited.replace(b'enemydamage 150',b'enemydamage 175')
        self.assertEqual(world.world_settings(world.metadata(custom)['keys'])['combatDifficulty'],'custom')
        self.assertEqual(world.patch_settings(custom,{'combatDifficulty':'custom'}),custom)
        for value in (True,[], 'impossible'):
            with self.assertRaises(ValueError):world.patch_settings(raw,{'combatDifficulty':value})
        self.w.save([],lambda:None,settings={'combatDifficulty':'easy','raidFrequency':'none'})
        loaded=world.World(self.path)
        self.assertEqual(loaded.public()['settings']['combatDifficulty'],'easy')
        self.assertEqual(loaded.public()['settings']['raidFrequency'],'none')

    def test_progression_roundtrip_preserves_unknown_keys_and_world_data(self):
        prefix=world.p('i',1)+world.p('hh',7,-9)+world.p('i',123)
        tail=b'location data preserved'
        zone=prefix+world.p('i',2)+world.string('defeated_eikthyr')+world.string('mod_unknown Value')+tail
        packed=world.gzip.compress(zone,mtime=0)
        suffix=world.p('f',99)+world.string('army_theelder')+world.p('ffff',5,1,2,3)+b'persistent events'
        raw=world.p('id',42,12345)+world.p('i',len(packed))+packed+suffix
        self.assertEqual(world.patch_progression(raw,{'defeated_eikthyr':True}),raw)
        edited=world.patch_progression(raw,{'defeated_eikthyr':False,'defeated_gdking':True})
        state=world.progression_state(edited)
        self.assertEqual(state['keys'],['mod_unknown Value','defeated_gdking'])
        self.assertTrue(state['data'].startswith(prefix));self.assertTrue(state['data'].endswith(tail))
        self.assertTrue(edited.endswith(suffix));self.assertEqual(raw[:12],edited[:12])
        for changes in ({'mod_unknown':False},{'defeated_gdking':'yes'},[]):
            with self.assertRaises(ValueError):world.patch_progression(raw,changes)
        with self.assertRaises((ValueError,OSError,EOFError)):world.progression_state(raw[:20])
        (self.path/'_main.1.db2').write_bytes(raw)
        loaded=world.World(self.path)
        settings=loaded.public()['settings']
        self.assertTrue(settings['progression']['defeated_eikthyr'])
        self.assertIsNone(loaded.build([],settings=settings))
        settings['progression']['defeated_gdking']=True
        settings['endRaid']=True;settings['resetRaidTimer']=True
        loaded.save([],lambda:None,settings=settings)
        reopened=world.World(self.path)
        self.assertTrue(reopened.public()['settings']['progression']['defeated_gdking'])
        self.assertIn('mod_unknown Value',reopened.public()['progressionKeys'])
        self.assertEqual(reopened.raid['name'],'');self.assertEqual(reopened.raid['timer'],0)
        for key in world.PROGRESSION_FLAGS:
            with self.subTest(flag=key):
                changed=world.patch_progression(raw,{key:True})
                self.assertIn(key,world.progression_state(changed)['keys'])
                cleared=world.patch_progression(changed,{key:False})
                self.assertNotIn(key,world.progression_state(cleared)['keys'])
                self.assertIn('mod_unknown Value',world.progression_state(cleared)['keys'])
        for key in ('activebosses','hildir1','defeated_frozenking_p3'):
            with self.assertRaises(ValueError):world.patch_progression(raw,{key:True})

    def test_raid_actions_preserve_other_world_data(self):
        prefix=world.p('id',42,12345.0)+world.p('i',6)+b'opaque'
        suffix=b'persistent events preserved'
        raw=prefix+world.p('f',900.0)+world.string('army_eikthyr')+world.p('ffff',25.0,1.0,2.0,3.0)+suffix
        self.assertEqual(world.patch_raid(raw,{}),raw)
        reset=world.patch_raid(raw,{'resetRaidTimer':True})
        self.assertEqual(world.raid_state(reset)['timer'],0)
        self.assertEqual(world.raid_state(reset)['name'],'army_eikthyr')
        end=world.patch_raid(raw,{'endRaid':True})
        self.assertEqual(world.raid_state(end)['name'],'')
        self.assertEqual(world.raid_state(end)['timer'],900)
        self.assertTrue(end.startswith(prefix));self.assertTrue(end.endswith(suffix))
        self.w.files['_main.1.db2']=raw
        number,files=self.w.build([],settings={'endRaid':True,'resetRaidTimer':True})
        self.assertEqual(world.raid_state(files[f'_main.{number}.db2'])['timer'],0)
        self.assertEqual(files[f'_main.{number}.fwl2'],self.w.files['_main.1.fwl2'])
        with self.assertRaises(ValueError):world.patch_raid(raw,{'endRaid':'yes'})
        with self.assertRaises(ValueError):world.patch_raid(b'truncated',{'endRaid':True})
        (self.path/'_main.1.db2').write_bytes(raw)
        loaded=world.World(self.path)
        loaded.save([],lambda:None,settings={'endRaid':True,'resetRaidTimer':True})
        reopened=world.World(self.path)
        self.assertEqual(reopened.public()['raid']['name'],'')
        self.assertEqual(reopened.public()['raid']['timer'],0)
        self.assertTrue(reopened.files[f'_main.{reopened.number}.db2'].endswith(suffix))

    def with_text_objects(self):
        def obj(prefab,creator,text=None,conn=None):
            flags=32|(64 if text is not None else 0)|(1 if conn else 0)
            b=world.p('Hfffi',flags,1.,2.,3.,world.hashcode(prefab))
            if conn:b+=world.p('Bi',conn,9876)
            b+=bytes([1])+world.p('iq',world.hashcode('creator'),creator)
            if text is not None:b+=bytes([1])+world.p('i',world.hashcode('text' if prefab=='sign' else 'tag'))+world.string(text)
            return b
        objects=[obj('sign',123,'Hello'),obj('portal_wood',123,'Home',1),obj('portal_wood',123,'Home',17),obj('sign',0,'Natural'),obj('sign',123),obj('portal_wood',123)]
        (self.path/'00_01__0_1.chunk').write_bytes(world.p('hi',42,len(objects))+b''.join(objects))
        (self.path/'_main.1.chunks').write_bytes(world.p('hiiHBIi',42,len(objects),1,1,0,1,len(objects)))
        self.w=world.World(self.path)
    def test_signs_portals_and_missing_text_fields(self):
        self.with_text_objects()
        self.assertEqual(len(self.w.texts),5)
        self.assertIsNone(self.w.build([],text_changes=[dict(id=t['id'],text=t['text']) for t in self.w.texts]))
        changes=[dict(id='0',text='Welcome – home'),dict(id='1',text='New home'),dict(id='3',text='Added text'),dict(id='4',text='New portal')]
        self.w.save([],lambda:None,text_changes=changes)
        self.assertEqual([t['text'] for t in self.w.texts],['Welcome – home','New home','Home','Added text','New portal'])
        self.assertIsNone(self.w.texts[1]['connection'])
        self.assertIsNone(self.w.texts[2]['connection'])
        self.assertIsNone(self.w.build([],text_changes=[dict(id=t['id'],text=t['text']) for t in self.w.texts]))
    def test_invalid_text_is_rejected(self):
        self.with_text_objects()
        for value in ('x'*501,'bad\x00text',123):
            with self.assertRaises(ValueError):self.w.build([],text_changes=[dict(id='0',text=value)])
    def test_truncated_chunk_rejected(self):
        with self.assertRaises(ValueError):world.parse_chunk(self.w.files['00_01__0_1.chunk'][:-1])
    def test_torn_newest_marker_opens_previous_generation_and_save_recovers(self):
        number,files=self.w.build(self.changes())
        for name,data in files.items():(self.path/name).write_bytes(b'' if name.endswith('.ok') else data)
        reopened=world.World(self.path)
        self.assertEqual(reopened.number,1)
        self.assertIn('never finished',reopened.public()['warning'])
        result=reopened.save(self.changes(),lambda:None)
        self.assertGreater(result['generation'],number)
        self.assertEqual(world.World(self.path).containers[0]['items'][0]['stack'],11)
    def test_complete_marker_with_unknown_version_fails_closed(self):
        number,files=self.w.build(self.changes())
        for name,data in files.items():(self.path/name).write_bytes(world.p('i',43) if name.endswith('.ok') else data)
        with self.assertRaisesRegex(ValueError,'commit marker'):world.World(self.path)
    def test_publish_never_replaces_an_existing_marker(self):
        src=self.path/'.staged';src.write_bytes(b'new');dst=self.path/'_main.1.ok'
        with self.assertRaises(FileExistsError):world.publish_new(src,dst)
        self.assertEqual(dst.read_bytes(),world.p('i',42))
    def test_publish_without_hard_links_falls_back_to_checked_rename(self):
        import errno,platforms
        if platforms.WINDOWS:self.skipTest('Windows always renames')
        src=self.path/'.staged';src.write_bytes(b'new');dst=self.path/'_main.9.ok'
        with patch.object(platforms.os,'link',side_effect=OSError(errno.EPERM,'no hard links')):world.publish_new(src,dst)
        self.assertEqual((dst.read_bytes(),src.exists()),(b'new',False))
    def test_no_complete_generation_is_an_error(self):
        (self.path/'_main.1.ok').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'No complete world generation'):world.World(self.path)
    def test_marker_failure_leaves_no_new_generation(self):
        real=world.durable
        def fail(path,data,created=None):
            if path.name.endswith('.ok.tmp'):
                real(path,data[:2],created);raise OSError('power cut while writing the marker')
            real(path,data,created)
        with patch.object(world,'durable',side_effect=fail),self.assertRaises(OSError):self.w.save(self.changes(),lambda:None)
        self.assertEqual(world.generations(self.path),[1])
        self.assertEqual(sorted(p.name for p in self.path.iterdir() if p.name.startswith(('_main.2','.'))),['.rune-backups'])
    def test_refresh_failure_after_commit_reports_success_with_warning(self):
        with patch.object(world,'World',side_effect=ValueError('boom')):result=self.w.save(self.changes(),lambda:None)
        self.assertFalse(result['unchanged'])
        self.assertTrue(result['reopen'])
        self.assertIn('Reopen the world',result['warning'])
        self.assertEqual(world.generations(self.path),[1,result['generation']])
        with self.assertRaisesRegex(ValueError,'changed since opening'):self.w.save(self.changes(),lambda:None)
    def test_marker_completed_in_place_after_opening_counts_as_a_change(self):
        number,files=self.w.build(self.changes())
        for name,data in files.items():(self.path/name).write_bytes(b'' if name.endswith('.ok') else data)
        stale=world.World(self.path);self.assertEqual(stale.number,1)
        (self.path/f'_main.{number}.ok').write_bytes(files[f'_main.{number}.ok'])
        with self.assertRaisesRegex(ValueError,'changed since opening'):stale.save([],lambda:None,settings={'nobuildcost':True})
    def test_retagging_unlinks_peer_portal_without_creator(self):
        def portal(creator,tag):
            return world.p('Hfffi',1|32|64,1.,2.,3.,world.hashcode('portal_wood'))+world.p('Bi',1,4242)+bytes([1])+world.p('iq',world.hashcode('creator'),creator)+bytes([1])+world.p('i',world.hashcode('tag'))+world.string(tag)
        objects=[portal(123,'Home'),portal(0,'Home')]
        (self.path/'00_01__0_1.chunk').write_bytes(world.p('hi',42,2)+b''.join(objects))
        (self.path/'_main.1.chunks').write_bytes(world.p('hiiHBIi',42,2,1,1,0,1,2))
        self.w=world.World(self.path)
        self.assertEqual((len(self.w.texts),len(self.w.links)),(1,2))
        self.w.save([],lambda:None,text_changes=[dict(id='0',text='Away')])
        self.assertEqual(self.w.links,[])
    def test_unsupported_container_has_empty_items(self):
        inv=world.p('iH',999,0)
        obj=world.p('Hfffi',0xa0,1.,2.,3.,world.hashcode('piece_chest_wood'))+bytes([1])+world.p('iq',world.hashcode('creator'),5)+bytes([1])+world.p('ii',world.hashcode('items'),len(inv))+inv
        _,containers=world.parse_chunk(world.p('hi',42,1)+obj)
        self.assertEqual((containers[0]['items'],'Unsupported inventory version' in containers[0]['error']),([],True))

if __name__=='__main__':unittest.main()

