"""Armour stand format checks use synthetic fixtures; never edit live saves."""
import copy, unittest
import test_world
from test_world import world

class StandTests(unittest.TestCase):
    def setUp(self):
        test_world.WorldTests.setUp(self)
        self.item.update(prefab='ArmorBronzeChest',prefab_hash=world.hashcode('ArmorBronzeChest'),stack=1,grid_x=4,grid_y=2)
        blob=bytes([110])+world.encode_inventory(110,[self.item],[])[6:]
        self.stand=world.p('Hfffi',0xb2,100.,3.,200.,world.hashcode('ArmorStand_Male'))
        self.stand+=world.num(1)+world.p('if',world.hashcode('health'),500.)
        self.stand+=world.num(3)+world.p('ii',world.hashcode('0_item'),world.hashcode('ArmorBronzeChest'))+world.p('ii',world.hashcode('0_variant'),0)+world.p('ii',world.hashcode('pose'),4)
        self.stand+=world.num(1)+world.p('iq',world.hashcode('creator'),123)
        self.stand+=world.num(2)+world.p('ii',world.hashcode('0_itemData'),len(blob))+blob+world.p('ii',world.hashcode('mod_data'),3)+b'xyz'
        chunk=world.p('hi',42,3)+self.stand+self.w.files['00_01__0_1.chunk'][6:]
        (self.path/'00_01__0_1.chunk').write_bytes(chunk)
        (self.path/'_main.1.chunks').write_bytes(world.p('hiiHBIi',42,3,1,1,0,1,3))
        self.w=world.World(self.path)
    def test_noop_and_load(self):
        c=self.w.containers[0]
        self.assertEqual(c['kind'],'stand');self.assertEqual(len(c['slots']),9)
        self.assertEqual(c['items'][0]['grid_x'],0)
        self.assertEqual(c['items'][0]['_stand_grid'],[4,2])
        self.assertIsNone(self.w.build([dict(id='0',items=c['items'])]))
    def test_edit_and_preserve_unknown_data(self):
        items=copy.deepcopy(self.w.containers[0]['items']);items[0].update(quality=3,durability=200)
        self.w.save([dict(id='0',items=items)],lambda:None)
        c=world.World(self.path).containers[0];i=c['items'][0]
        self.assertEqual(i['quality'],3);self.assertEqual(i['durability'],200)
        self.assertEqual(i['_stand_grid'],[4,2]);self.assertEqual(i['custom_data'],{'mod':'preserve'})
        self.assertEqual(i['crafter_name'],'Viking');self.assertEqual(i['_cheat_byte'],129)
        self.assertIn((world.hashcode('mod_data'),(world.p('i',3)+b'xyz').hex()),c['groups'][128])
        self.assertIn((world.hashcode('pose'),world.p('i',4).hex()),c['groups'][16])
        self.assertEqual(self.w.containers[1]['items'][0]['stack'],10)
    def test_remove_and_add_compatible_slot(self):
        c=self.w.containers[0];items=copy.deepcopy(c['items'])
        item=copy.deepcopy(items[0]);item.pop('_raw');item.update(prefab='HelmetBronze',prefab_hash=world.hashcode('HelmetBronze'),grid_x=2)
        self.w.save([dict(id='0',items=[item])],lambda:None)
        loaded=world.World(self.path).containers[0]['items']
        self.assertEqual(len(loaded),1);self.assertEqual(loaded[0]['prefab'],'HelmetBronze');self.assertEqual(loaded[0]['grid_x'],2)
    def test_reject_incompatible_and_duplicate_slots(self):
        items=copy.deepcopy(self.w.containers[0]['items']);items[0]['prefab']='Wood'
        with self.assertRaisesRegex(ValueError,'cannot be attached'):self.w.build([dict(id='0',items=items)])
        items=copy.deepcopy(self.w.containers[0]['items']);items.append(copy.deepcopy(items[0]))
        with self.assertRaisesRegex(ValueError,'slot'):self.w.build([dict(id='0',items=items)])
    def test_missing_payload_readonly(self):
        raw=world.p('hi',42,1)+world.p('Hfffi',0x30,1.,2.,3.,world.hashcode('ArmorStand_Male'))+world.num(1)+world.p('ii',world.hashcode('0_item'),world.hashcode('ArmorBronzeChest'))+world.num(1)+world.p('iq',world.hashcode('creator'),123)
        _,entries=world.parse_chunk(raw);self.assertIn('error',entries[0])
    def test_empty_stand_adds_missing_groups(self):
        raw=world.p('hi',42,1)+world.p('Hfffi',0x20,1.,2.,3.,world.hashcode('ArmorStand_Male'))+world.num(1)+world.p('iq',world.hashcode('creator'),123)
        _,entries=world.parse_chunk(raw);c=entries[0];item=copy.deepcopy(self.item);item.update(grid_x=0,grid_y=0)
        edited=world.encode_stand(c,[item],raw)
        _,again=world.parse_chunk(world.p('hi',42,1)+edited)
        self.assertEqual(again[0]['items'][0]['prefab'],'ArmorBronzeChest')

if __name__=='__main__':unittest.main()
