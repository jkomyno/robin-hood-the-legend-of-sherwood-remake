import unittest
from terrain_clip import area, clip, prism
from floor_contacts import extension, cutters


class TerrainClipTests(unittest.TestCase):
    def setUp(self):
        self.cutter = prism([(0,0,5),(10,0,5),(0,10,5)], 'terrain')

    def test_buried_wall_is_trimmed_and_uvs_interpolate(self):
        tri = [(1,1,0,0,0),(2,1,10,1,1),(1,1,10,0,1)]
        kept, removed = clip(tri, [self.cutter])
        self.assertAlmostEqual(sum(area(p) for p in kept)+sum(area(p) for p,_ in removed),area(tri))
        for p in kept:
            for v in p:
                self.assertGreaterEqual(v[2],5)
                self.assertAlmostEqual(v[4],v[2]/10)
        self.assertTrue(removed)

    def test_partial_footprint_preserves_exposed_lower_wall(self):
        tri = [(-5,1,0),(5,1,0),(5,1,10)]
        kept, removed = clip(tri, [self.cutter])
        self.assertTrue(any(v[0]<0 and v[2]<5 for p in kept for v in p))
        self.assertTrue(all(v[0]>=0 for p,_ in removed for v in p))
        self.assertAlmostEqual(sum(area(p) for p in kept)+sum(area(p) for p,_ in removed),area(tri))

    def test_sloped_support_cuts_to_the_plane(self):
        cutter=prism([(0,0,2),(10,0,12),(0,10,2)],'slope')
        tri=[(1,1,0),(2,1,10),(1,1,10)]
        kept,removed=clip(tri,[cutter])
        self.assertTrue(removed)
        self.assertTrue(all(v[2]>=v[0]+2-1e-6 for p in kept for v in p))

    def test_coplanar_top_and_outside_geometry_are_preserved(self):
        for tri in [[(1,1,5),(2,1,5),(1,2,5)],[(20,1,0),(21,1,0),(20,2,0)],
                    [(1,1,-5),(2,1,-5),(1,2,-5)]]:
            self.assertEqual(clip(tri,[self.cutter]),([tri],[]))

    def test_overlapping_supports_do_not_remove_surface_twice(self):
        tri=[(1,1,0),(2,1,10),(1,1,10)]
        self.assertEqual(clip(tri,[self.cutter,self.cutter]),clip(tri,[self.cutter]))

    def test_near_zero_underside_is_removed_despite_quantization(self):
        for z in [0, -.00005, .00005]:
            tri=[(1,1,z),(2,1,z),(1,2,z)]
            kept,removed=clip(tri,[self.cutter])
            self.assertEqual(kept,[])
            self.assertAlmostEqual(sum(area(p) for p,_ in removed),area(tri))

    def test_frontage_floor_removes_foundation_outside_terrain_footprint(self):
        # Terrain ends at Y=0; the lodge sits behind it, so footprint clipping
        # alone misses the foundation. Its explicitly reviewed floor fills it.
        terrain = prism([(0,-10,5),(10,-10,5),(0,0,5)], 'courtyard')
        wall = [(1,1,0,0,0),(2,1,10,1,1),(1,1,10,0,1)]
        self.assertEqual(clip(wall,[terrain]),([wall],[]))
        import math
        floor = extension('lodge',wall,{'floor_game_z':5*math.cos(math.radians(35))})
        kept, removed = clip(wall,[terrain]+cutters(floor))
        self.assertTrue(removed)
        self.assertTrue(all(v[2]>=5-1e-6 for p in kept for v in p))
        for p in kept:
            for v in p:
                self.assertAlmostEqual(v[4],v[2]/10)

    def test_floor_continuation_is_bounded_to_its_asset(self):
        floor = extension('lodge',[(0,0,0),(5,5,10)],{'floor_game_z':5})
        river_wall = [(20,1,0),(21,1,0),(20,1,10)]
        self.assertEqual(clip(river_wall,cutters(floor)),([river_wall],[]))

    def test_lane_continuation_clamps_to_lower_street_and_preserves_uvs(self):
        import math
        from floor_contacts import height_at
        cosine, sine = math.cos(math.radians(35)), math.sin(math.radians(35))
        contact = {'floor_game_z':5*cosine,
                   'plane_game_z':[.5*cosine,-.25*cosine/sine,2*cosine]}
        wall = [(0,1,0,0),(10,1,12,1),(0,1,12,1)]
        floor = extension('lane-house',wall,contact)
        kept, removed = clip(wall,cutters(floor))
        self.assertTrue(kept)
        self.assertTrue(removed)
        self.assertAlmostEqual(height_at(contact,0,1),5)
        self.assertAlmostEqual(height_at(contact,10,1),7.25)
        self.assertAlmostEqual(sum(area(p) for p in kept)+sum(area(p) for p,_ in removed),area(wall))
        for p in kept:
            for v in p:
                self.assertGreaterEqual(v[2],max(5,.5*v[0]+.25*v[1]+2)-1e-6)
                self.assertAlmostEqual(v[3],v[2]/12)


if __name__ == '__main__':
    unittest.main()
