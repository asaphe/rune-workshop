import copy, unittest
import test_stands
from test_world import world

class RefinementSaveTests(unittest.TestCase):
    def setUp(self):test_stands.StandTests.setUp(self)
    def test_refined_stand_and_container_quality_survives_save(self):
        changes=[]
        for c in self.w.containers:
            items=copy.deepcopy(c['items']);items[0]['quality']=12;items[0]['durability']=900
            changes.append(dict(id=c['id'],items=items))
        self.w.save(changes,lambda:None)
        loaded=world.World(self.path)
        for c in loaded.containers:
            self.assertEqual(c['items'][0]['quality'],12)
            self.assertEqual(c['items'][0]['durability'],900)
            self.assertEqual(c['items'][0]['custom_data'],{'mod':'preserve'})
