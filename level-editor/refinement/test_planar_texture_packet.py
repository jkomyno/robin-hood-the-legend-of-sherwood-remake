import unittest
import numpy as np
from prepare_planar_texture_packet import coverage

class CoverageTests(unittest.TestCase):
    def test_full_plane_has_no_diagonal_crack(self):
        triangles=np.array([[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]])
        self.assertTrue(coverage(triangles,32,16).all())

    def test_gap_and_outside_are_not_editable(self):
        triangles=np.array([[[0,0],[.25,0],[.25,1]],[[0,0],[.25,1],[0,1]],
                            [[.75,0],[1,0],[1,1]],[[.75,0],[1,1],[.75,1]]])
        surface=coverage(triangles,32,16)
        self.assertTrue(surface[:,:8].all())
        self.assertFalse(surface[:,8:24].any())
        self.assertTrue(surface[:,24:].all())

    def test_degenerate_uv_fails(self):
        with self.assertRaises(ValueError):coverage(np.zeros((1,3,2)),32,16)

if __name__=='__main__': unittest.main()

class FillGuardTests(unittest.TestCase):
    def test_unknown_only_allowed(self):
        from planar_texture_guards import validate_fill
        original=np.full((4,4,4),255,np.uint8);generated=original.copy();mask=original.copy();mask[1,1,3]=0;generated[1,1,:3]=0
        self.assertEqual(validate_fill(original,generated,mask,np.ones((4,4),bool)),1)
        generated[0,0,0]=0
        with self.assertRaises(ValueError):validate_fill(original,generated,mask,np.ones((4,4),bool))

    def test_hole_may_not_be_exposed(self):
        from planar_texture_guards import validate_fill
        original=np.full((4,4,4),255,np.uint8);mask=original.copy();mask[1,1,3]=0;surface=np.ones((4,4),bool);surface[1,1]=False
        with self.assertRaises(ValueError):validate_fill(original,original,mask,surface)

class AuditedGeometryTests(unittest.TestCase):
    def write_glb(self,directory,positions,alpha='OPAQUE'):
        import json,struct
        from pathlib import Path
        arrays=[np.array(positions,dtype='<f4'),np.array([[0,0],[1,0],[1,1],[0,1]],dtype='<f4'),np.array([0,1,2,0,2,3],dtype='<u2')]
        chunks=[];views=[];offset=0
        for a in arrays:
            b=a.tobytes();views.append({'buffer':0,'byteOffset':offset,'byteLength':len(b)});chunks.append(b);offset+=len(b)
        data={'meshes':[{'primitives':[{'attributes':{'POSITION':0,'TEXCOORD_0':1},'indices':2,'material':0}]}],
              'materials':[{'alphaMode':alpha}],'bufferViews':views,'accessors':[
                  {'bufferView':0,'componentType':5126,'count':4,'type':'VEC3'},
                  {'bufferView':1,'componentType':5126,'count':4,'type':'VEC2'},
                  {'bufferView':2,'componentType':5123,'count':6,'type':'SCALAR'}]}
        js=json.dumps(data).encode();js+=b' '*((-len(js))%4);binary=b''.join(chunks);binary+=b'\0'*((-len(binary))%4)
        raw=struct.pack('<III',0x46546c67,2,28+len(js)+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary
        p=Path(directory)/'asset.glb';p.write_bytes(raw);return p

    def test_planar_uvs_accepted_nonplanar_and_physical_alpha_rejected(self):
        import tempfile
        from prepare_planar_texture_packet import atlas_triangles
        with tempfile.TemporaryDirectory() as d:
            points=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]
            self.assertEqual(atlas_triangles(self.write_glb(d,points)).shape,(2,3,2))
            with self.assertRaises(ValueError):atlas_triangles(self.write_glb(d,points,'MASK'))
            points[3][2]=.1
            with self.assertRaises(ValueError):atlas_triangles(self.write_glb(d,points))
