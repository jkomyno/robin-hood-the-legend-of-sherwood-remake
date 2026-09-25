import copy
import unittest
from texture_triangle_partition import verify


def triangle(ids):
    positions=[(0,0,0),(1,0,0),(1,1,0),(0,1,0)]
    return dict(material=False,corners=[dict(position=positions[i],uv={'UV':positions[i][:2]}) for i in ids])


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.before={'wall':dict(invariants={'matrix':'exact','uv_names':['UV']},edges=[(0,1),(1,2),(2,3),(0,3)],
            polygons=[dict(polygon=(0,1,2,3),triangles=[triangle([0,1,2]),triangle([0,2,3])])])}
        self.after=copy.deepcopy(self.before)
        self.after['wall']['edges'].append((0,2))
        self.after['wall']['polygons']=[dict(polygon=t,triangles=[triangle(t)]) for t in [(0,1,2),(0,2,3)]]
        self.proof=dict(scoped_oriented_triangles={'wall':2},original_polygon_by_new_polygon=[0,0])

    def test_same_oriented_surface_passes(self):
        self.assertEqual(verify(self.before,self.after,self.proof)['status'],'PASS')

    def test_rejects_shape_winding_uv_and_transform(self):
        for kind in ['position','uv','winding','matrix']:
            after=copy.deepcopy(self.after)
            tri=after['wall']['polygons'][0]['triangles'][0]
            if kind=='position':tri['corners'][0]['position']=(0,0,1)
            elif kind=='uv':tri['corners'][0]['uv']['UV']=(.5,.5)
            elif kind=='winding':tri['corners'].reverse()
            else:after['wall']['invariants']['matrix']='changed'
            with self.subTest(kind=kind), self.assertRaises(ValueError):verify(self.before,after,self.proof)

    def test_rejects_scope_and_extra_edges(self):
        proof=copy.deepcopy(self.proof);proof['scoped_oriented_triangles']['wall']=3
        with self.assertRaises(ValueError):verify(self.before,self.after,proof)
        after=copy.deepcopy(self.after);after['wall']['edges'].append((1,3))
        with self.assertRaises(ValueError):verify(self.before,after,self.proof)

    def test_rejects_unscoped_polygon_change(self):
        before=copy.deepcopy(self.before);after=copy.deepcopy(self.after)
        p=dict(polygon=(0,1,2),triangles=[triangle([0,1,2])])
        before['wall']['polygons'].append(p);after['wall']['polygons'].append(copy.deepcopy(p))
        proof=copy.deepcopy(self.proof);proof['original_polygon_by_new_polygon'].append(1)
        after['wall']['polygons'][-1]['triangles'][0]['corners'].reverse()
        with self.assertRaises(ValueError):verify(before,after,proof)

if __name__=='__main__':unittest.main()
