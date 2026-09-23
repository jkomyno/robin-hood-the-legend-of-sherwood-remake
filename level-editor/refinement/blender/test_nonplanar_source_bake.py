"""Blender regression: warped polygons use their rendered triangle normals."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_projection_bake import bake


class NonplanarBakeTests(unittest.TestCase):
    def run_fixture(self, vertices):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = 'NormalFixture' + str(len(bpy.data.collections))
            collection = bpy.data.collections.new(name + ' Working')
            bpy.context.scene.collection.children.link(collection)
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
            obj = bpy.data.objects.new(name, mesh)
            obj['source_node'] = 'fixture'
            collection.objects.link(obj)
            image = bpy.data.images.new(name, width=128, height=128)
            image.pixels[:] = [1, 0, 0, 1] * (128 * 128)
            image.filepath_raw = str(root / 'source.png')
            image.file_format = 'PNG'
            image.save()
            toward = Vector((0, -math.cos(math.radians(35)), math.sin(math.radians(35))))
            calls = []
            def sample(obj, normal, positions, accepted, colors):
                calls.append((normal.dot(toward), int(accepted.sum()), len(accepted)))
                colors[~accepted, :3] = (0, 1, 0)
            before = ([tuple(v.co) for v in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons])
            result = bake(name, root / 'source.png', root / 'report.json', hidden_sampler=sample)
            self.assertEqual(before, ([tuple(v.co) for v in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons]))
            atlas = next(n.image for n in mesh.materials[-1].node_tree.nodes if n.type == 'TEX_IMAGE')
            pixels = np.asarray(atlas.pixels[:]).reshape(-1, 4)
            self.assertTrue(np.any(np.all(pixels[:, :3] == (1, 0, 0), axis=1)))
            return calls, result

    def test_warped_face_retains_front_triangle_source(self):
        # A quad whose averaged normal rejects the source, although one of its
        # rendered triangles is visible. Translation keeps samples in the atlas.
        vertices = [(49.06848, -70.47803, 28.08863), (18.27258, -49.40625, 1.46493),
                    (10.74896, -60.40210, 3.05194), (41.62665, -81.52979, 35.24903)]
        calls, result = self.run_fixture(vertices)
        self.assertTrue(any(cos > .05 and known > 0 for cos, known, total in calls))
        self.assertTrue(any(cos < .05 and known == 0 for cos, known, total in calls))
        self.assertGreater(result['known_texels'], 0)
        self.assertGreater(result['unknown_texels'], 0)

    def test_planar_face_source_unchanged(self):
        calls, result = self.run_fixture([(10, -30, 5), (30, -30, 5), (30, -10, 5), (10, -10, 5)])
        self.assertTrue(all(abs(cos - math.sin(math.radians(35))) < 1e-6 for cos, _, _ in calls))
        self.assertEqual(result['unknown_texels'], 0)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NonplanarBakeTests))
    if not result.wasSuccessful():
        raise RuntimeError('Nonplanar source bake tests failed')
