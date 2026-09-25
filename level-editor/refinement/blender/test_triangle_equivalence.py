import copy
import unittest
from triangle_equivalence import verify_equivalence


def scene():
    corners = [dict(position=p, uv={'source': uv}) for p, uv in [((0,0,0),(0,0)),((1,0,0),(1,0)),((1,1,1),(1,1)),((0,1,0),(0,1))]]
    triangles = [dict(corners=[corners[i] for i in ids], material='masonry') for ids in [(0,1,2),(0,2,3)]]
    return {'stair': dict(invariants={'vertices': [c['position'] for c in corners], 'source_image_sha256': 'bound'}, polygons={0:dict(polygon=[0,1,2,3],triangles=triangles),1:dict(polygon=[0,1,2],triangles=copy.deepcopy(triangles[:1]))}), 'neighbor': {'hash':'exact'}}


class TriangleEquivalenceTests(unittest.TestCase):
    def test_nonplanar_tessellation_exact(self):
        old=scene();new=copy.deepcopy(old)
        new['stair']['polygons'][0]['polygon']=[[0,1,2],[0,2,3]]
        new['stair']['polygons'][0]['triangles'].reverse()
        for t in new['stair']['polygons'][0]['triangles']:
            t['corners']=t['corners'][1:]+t['corners'][:1]
        self.assertEqual(verify_equivalence(old,new,{'stair':[0]})['status'],'PASS')

    def test_rejects_surface_winding_uv_material_and_neighbor_drift(self):
        mutations=[lambda s:s['stair']['polygons'][0]['triangles'][0]['corners'].reverse(),
                   lambda s:s['stair']['polygons'][0]['triangles'][0].update(material='other'),
                   lambda s:s['stair']['polygons'][0]['triangles'][0]['corners'][0].update(position=(0,0,.001)),
                   lambda s:s['stair']['polygons'][0]['triangles'][0]['corners'][0].update(uv={'source':(.01,0)}),
                   lambda s:s['neighbor'].update(hash='changed'),
                   lambda s:s['stair']['polygons'][1].update(polygon=[2,1,0]),
                   lambda s:s['stair']['invariants'].update(source_image_sha256='changed')]
        for mutate in mutations:
            old=scene();new=copy.deepcopy(old);mutate(new)
            with self.assertRaises(ValueError):verify_equivalence(old,new,{'stair':[0]})

    def test_rejects_duplicate_missing_triangle(self):
        old=scene();new=copy.deepcopy(old);new['stair']['polygons'][0]['triangles'].pop()
        with self.assertRaises(ValueError):verify_equivalence(old,new,{'stair':[0]})

if __name__=='__main__':unittest.main()
