import copy
import unittest
import server
import test_survival


class StatisticsTests(unittest.TestCase):
    def fixture(self, version=34):
        raw, _ = test_survival.SurvivalTests().fixture(version)
        root, player = server.decode(raw)
        root['profiles'][6]['pickable_stats'] = {'Pickable_Mushroom': 4}
        raw = server.encode(root, player)
        return raw, server.open_save(raw, 'stats.fch')

    def test_roundtrip_and_only_requested_counters_change(self):
        for version in (33, 34):
            raw, data = self.fixture(version)
            self.assertEqual(server.export_save(data), raw)
            before, player = server.decode(raw)
            data['statistics'][6]['counters']['125'] = 500
            data['statistics'][6]['pickable_stats']['Pickable_Mushroom'] = 45
            after, edited = server.decode(server.export_save(data))
            expected = copy.deepcopy(before)
            expected['profiles'][6]['stats'][125] = 500
            expected['profiles'][6]['pickable_stats']['Pickable_Mushroom'] = 45
            self.assertEqual(after, expected)
            self.assertEqual(edited, player)

    def test_bad_values_and_unknown_keys_rejected(self):
        for value in (-1, 1.5, True, float('nan'), float('inf'), 16777217, '10'):
            _, data = self.fixture()
            data['statistics'][6]['counters']['125'] = value
            with self.assertRaises(ValueError): server.export_save(data)
        _, data = self.fixture()
        data['statistics'][6]['counters']['128'] = 20
        with self.assertRaises(ValueError): server.export_save(data)
        _, data = self.fixture()
        data['statistics'][6]['pickable_stats']['invented'] = 20
        with self.assertRaises(ValueError): server.export_save(data)
