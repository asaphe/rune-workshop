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
        real=world.durable
        def fail(path,data):
            if path.suffix=='.fwl2':raise OSError('injected failure')
            real(path,data)
        with patch.object(world,'durable',side_effect=fail):
            with self.assertRaises(OSError):self.w.save(self.changes(),lambda:None)
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

if __name__=='__main__':unittest.main()

