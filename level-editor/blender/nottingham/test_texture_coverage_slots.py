"""Blender regression tests for different atlases on one receiver object."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from trace_texture_coverage_pixels import slot_provenance


class MaterialSlotProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        mesh = bpy.data.meshes.new('two-atlas fixture')
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [],
                         [(0, 1, 2), (0, 2, 3)])
        self.obj = bpy.data.objects.new('two-atlas receiver', mesh)
        bpy.context.scene.collection.objects.link(self.obj)
        self.addCleanup(lambda: bpy.data.objects.remove(self.obj, do_unlink=True))
        self.evidence = []
        for index, name in enumerate(('source-uv', 'generated-uv')):
            uv = mesh.uv_layers.new(name=name)
            for loop in uv.data:
                loop.uv = (.2 + index * .3, .25)
            image = bpy.data.images.new(name, width=2 + index, height=2, alpha=True)
            image.pixels.foreach_set([.2 + index * .4, .3, .4, 1] * (image.size[0] * 2))
            image.pack()
            material = bpy.data.materials.new(name)
            material.use_nodes = True
            material.node_tree.nodes.clear()
            texture = material.node_tree.nodes.new('ShaderNodeTexImage')
            texture.image = image
            uv_node = material.node_tree.nodes.new('ShaderNodeUVMap')
            uv_node.uv_map = name
            material.node_tree.links.new(uv_node.outputs['UV'], texture.inputs['Vector'])
            mesh.materials.append(material)
            mesh.polygons[index].material_index = index
            path = Path(self.directory.name) / f'{index}.npz'
            # The first face is unfilled while the second has generated color.
            np.savez_compressed(path, ownership=np.full((2, 2 + index), index * 2, dtype=np.uint8))
            proof = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),
                         uv_sha256=hashlib.sha256(json.dumps([list(v.uv) for v in uv.data]).encode()).hexdigest())
            self.evidence.append(dict(object=self.obj.name, slots=[index], provenance=proof))

    def test_distinct_materials_do_not_overwrite_object_ownership(self):
        arrays = slot_provenance(self.evidence, bpy.context.scene.objects)
        self.assertEqual(set(arrays), {(self.obj.name, 0, 'source-uv'),
                                      (self.obj.name, 1, 'generated-uv')})
        for face in self.obj.data.polygons:
            index = face.material_index
            key = (self.obj.name, index, ('source-uv', 'generated-uv')[index])
            self.assertEqual(int(arrays[key][0, 0]), index * 2)

    def test_wrong_slot_or_uv_is_rejected(self):
        wrong_slot = copy.deepcopy(self.evidence)
        wrong_slot[0]['slots'] = [1]
        with self.assertRaisesRegex(ValueError, 'image differs'):
            slot_provenance(wrong_slot, bpy.context.scene.objects)
        self.obj.data.uv_layers['source-uv'].data[0].uv = (.9, .9)
        with self.assertRaisesRegex(ValueError, 'UV differs'):
            slot_provenance(self.evidence, bpy.context.scene.objects)

    def test_duplicate_slot_or_changed_provenance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous material slot'):
            slot_provenance(self.evidence + [self.evidence[0]], bpy.context.scene.objects)
        path = Path(self.evidence[0]['provenance']['path'])
        np.savez_compressed(path, ownership=np.ones((2, 2), dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, 'Provenance changed'):
            slot_provenance(self.evidence, bpy.context.scene.objects)


if __name__ == '__main__':
    unittest.main(argv=[__file__])
