import unittest
from types import SimpleNamespace as NS
from material_states import apply_material_state


class MaterialStateTests(unittest.TestCase):
    def setUp(self):
        self.faces = [NS(index=0, material_index=0), NS(index=1, material_index=0)]
        self.obj = NS(name='room', type='MESH', data=NS(polygons=self.faces,
                      materials=[NS(name='room atlas'), NS(name='outer atlas')]))
        self.objects = {'room': self.obj}
        self.record = {'object': 'room', 'covered_face_materials': {
            '0': {'slot': 1, 'material': 'outer atlas'},
            '1': {'slot': 0, 'material': 'room atlas'}}, 'revealed_face_materials': {
            str(i): {'slot': 0, 'material': 'room atlas'} for i in range(2)}}

    def test_round_trip_retains_room_and_switches_only_declared_face(self):
        apply_material_state(self.objects, self.record, 'covered')
        self.assertEqual([f.material_index for f in self.faces], [1, 0])
        apply_material_state(self.objects, self.record, 'revealed')
        self.assertEqual([f.material_index for f in self.faces], [0, 0])

    def test_stale_slot_fails_before_any_material_mutation(self):
        self.record['covered_face_materials']['1']['material'] = 'stale atlas'
        with self.assertRaisesRegex(ValueError, 'reviewed material'):
            apply_material_state(self.objects, self.record, 'covered')
        self.assertEqual([f.material_index for f in self.faces], [0, 0])


if __name__ == '__main__':
    unittest.main()
