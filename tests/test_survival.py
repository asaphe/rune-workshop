import copy, unittest
from test_synthetic_saves import synthetic_fch
import server

class SurvivalTests(unittest.TestCase):
 def fixture(self,version=34):
  r,p=server.decode(synthetic_fch(version));r['stat_count']=205;r['profile_count']=10
  profile=r['profiles'][0];r['profiles']=[copy.deepcopy(profile) for _ in range(10)]
  for i,row in enumerate(r['profiles']):
   row['stats']=[float(i)]*205;row['stats'][128:130]=[2.,18.]
  raw=server.encode(r,p)
  return raw,server.open_save(raw,'synthetic.fch')
 def test_noop_and_targeted_roundtrip_both_versions(self):
  for version in (33,34):
   raw,data=self.fixture(version)
   self.assertEqual(server.export_save(data),raw)
   before,player=server.decode(raw)
   for i in (0,1,6):data['survival'][i]={'current':29,'best':29}
   after,edited=server.decode(server.export_save(data))
   expected=copy.deepcopy(before)
   for i in (0,1,6):expected['profiles'][i]['stats'][128:130]=[29.,29.]
   self.assertEqual(after,expected);self.assertEqual(edited,player)
 def test_invalid_values_rejected(self):
  for value in (-1,1.5,float('nan'),float('inf'),True,1000001):
   _,data=self.fixture();data['survival'][6]['current']=value
   with self.assertRaises(ValueError):server.export_save(data)
  _,data=self.fixture();data['survival'][6]={'current':29,'best':18}
  with self.assertRaises(ValueError):server.export_save(data)
 def test_short_layout_not_exposed(self):
  raw=synthetic_fch(34);data=server.open_save(raw,'synthetic.fch')
  self.assertIsNone(data['survival']);self.assertEqual(server.export_save(data),raw)
  data['survival']=[{'current':29,'best':29}]*10
  with self.assertRaises(ValueError):server.export_save(data)
