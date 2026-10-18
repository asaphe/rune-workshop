import copy,os,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,world
FIXTURES=Path(os.environ.get('RUNE_FIXTURES') or Path(__file__).resolve().parents[3]/'work/fixtures')
class RecoveryTests(unittest.TestCase):
 def test_multiple_graves_not_containers(self):
  item=dict(prefab='Wood',stack=5,quality=1,durability=1,grid_x=0,grid_y=0,world_level=0,variant=0)
  inv=world.encode_inventory(110,[item],[])
  def obj(owner,x):
   return world.p('Hfffi',0xa0,x,2.,3.,world.hashcode('Player_tombstone'))+bytes([1])+world.p('iq',world.hashcode('owner'),owner)+bytes([1])+world.p('ii',world.hashcode('items'),len(inv))+inv
  tombs=[];count,containers=world.parse_chunk(world.p('hi',42,3)+obj(123,1.)+obj(123,9.)+obj(456,8.),tombs=tombs)
  self.assertEqual(count,3);self.assertFalse(containers);self.assertEqual(len(tombs),3)
  self.assertEqual([g['position'][0] for g in tombs if g['owner']=='123'],[1.,9.])
 @unittest.skipUnless((FIXTURES/'current-v47.fch').exists(),'private save fixtures not available; set RUNE_FIXTURES')
 def test_select_owner_world_and_preserve_everything_else(self):
  raw=(FIXTURES/'current-v47.fch').read_bytes()
  data=server.open_save(raw,'test.fch');root,player=server.decode(raw)
  w=Mock();w.meta=dict(uid=str(root['worlds'][0]['world_id']),name='Test')
  owner=str(root['player_id']);w.tombs=[dict(owner=owner,position=[1.,2.,3.],items=[]),dict(owner=owner,position=[8.,9.,10.],items=[]),dict(owner='other',position=[4.,5.,6.],items=[])]
  with patch.object(server,'World',return_value=w):result=server.scan_tombstones(dict(session=data['session'],path='unused'))
  self.assertEqual(len(result['tombstones']),2)
  data['teleportTarget']=result['tombstones'][1]['id']
  output=server.export_save(data);after,p=server.decode(output)
  expected=copy.deepcopy(root);expected['worlds'][0]['logout_point']=[8.,9.,10.];expected['worlds'][0]['have_logout_point']=True
  self.assertEqual(after,expected);self.assertEqual(p,player)
  self.assertEqual(server.export_save(data),output)
  data['teleportTarget']=None;self.assertEqual(server.export_save(data),raw)
  data['teleportTarget']='forged'
  with self.assertRaises(ValueError):server.export_save(data)
  data['teleportTarget']=result['tombstones'][0]['id'];w.verify_source.side_effect=ValueError('changed')
  with self.assertRaises(ValueError):server.export_save(data)
if __name__=='__main__':unittest.main()
