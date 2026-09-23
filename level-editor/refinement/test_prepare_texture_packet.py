"""Synthetic approved packet preparation; never invokes generation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from prepare_texture_packet import prepare
from record_approval import record
from review_evidence import sha


class PreparationTests(unittest.TestCase):
    tile_size=(384,512)
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.packet=self.root/'modified';(self.packet/'views').mkdir(parents=True)
        (self.root/'model.blend').write_bytes(b'synthetic approved model')
        (self.root/'handoff.json').write_text('{}')
        self.manifest=self.root/'review.json'
        w,h=self.tile_size
        source_sheet=Image.new('RGBA',(w*4,h*2));solid_sheet=Image.new('RGBA',(w*4,h*2))
        views=[]
        for i in range(8):
            source=Image.new('RGBA',(w,h),(i*20,40,80,255))
            solid=Image.new('RGBA',(w,h),(128,128,128,0))
            solid.putpixel((1,1),(128,128,128,255));solid.putpixel((2,1),(128,128,128,255))
            known=Image.new('RGBA',(w,h),(0,0,0,255));known.putpixel((1,1),(255,255,255,255))
            for kind,image in [('textured',source),('solid',solid),('known',known)]:
                image.save(self.packet/'views'/f'view-{i}-{kind}.png')
            left,top=i%4*w,i//4*h
            source_sheet.paste(source,(left,top));solid_sheet.paste(solid,(left,top))
            views.append({'index':i,'ownership_sha256':sha(self.packet/'views'/f'view-{i}-known.png')})
        source_sheet.save(self.packet/'textured.png');solid_sheet.save(self.packet/'solid.png')
        (self.packet/'views.json').write_text(json.dumps({'asset_id':'fixture','tile_size':[w,h],
            'layout':{'columns':4,'rows':2},'views':views}))
        self.item={'id':'fixture','status':'ready-for-user','worker_status':'ready-for-user',
            'stored_material_validation':'PASS','workspace':str(self.root),
            'solid':str(self.packet/'solid.png'),'textured':str(self.packet/'textured.png')}
        evidence={k:{'path':str(p),'sha256':sha(p)} for k,p in
            [('solid',self.packet/'solid.png'),('textured',self.packet/'textured.png'),('frames',self.packet/'views.json')]}
        identity={'asset_id':'fixture','model_sha256':sha(self.root/'model.blend'),
                  'evidence':{k:v['sha256'] for k,v in evidence.items()}}
        self.item['revision']={'model_sha256':identity['model_sha256'],'evidence':evidence,
            'sha256':hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
        self.save()
        record(self.manifest,['fixture'],'Synthetic explicit geometry approval')

    def save(self,extra=None):
        self.manifest.write_text(json.dumps({'items':[self.item],**(extra or {})}))

    def test_exact_pixels_and_only_unknown_geometry_editable(self):
        result=prepare(self.manifest,'fixture',self.root/'output')
        self.assertEqual(result['editable_pixels'],8)
        self.assertEqual(sha(self.root/'output/input.png'),sha(self.packet/'textured.png'))
        mask=np.asarray(Image.open(self.root/'output/views/view-0-mask.png'))
        self.assertEqual(mask[1,2,3],0)
        self.assertEqual(mask[1,1,3],255)
        self.assertEqual(mask[0,0,3],255)

    def test_check_only_validates_without_output(self):
        result=prepare(self.manifest,'fixture',self.root/'dry-run',check_only=True)
        self.assertEqual(result['status'],'eligible')
        self.assertEqual(result['editable_pixels'],8)
        self.assertFalse((self.root/'dry-run').exists())

    def test_material_pending_or_issue_blocks_without_output(self):
        for field,value in [('stored_material_validation','pending-or-failed'),('generation_blocked',True),
                            ('texture_issue','incorrect atlas')]:
            with self.subTest(field=field):
                original=dict(self.item);self.item[field]=value;self.save()
                with self.assertRaises(ValueError):prepare(self.manifest,'fixture',self.root/'blocked')
                self.assertFalse((self.root/'blocked').exists());self.item=original
        self.save();(self.root/'handoff.json').write_text('{"texture_issue":"unresolved"}')
        with self.assertRaises(ValueError):prepare(self.manifest,'fixture',self.root/'blocked')

    def test_geometry_basis_approval_and_incomplete_other_asset(self):
        record(self.manifest,['fixture'],'Synthetic geometry basis approval',geometry_only=True)
        audit=self.root/'added-audit.json';audit.write_text('technical evidence only')
        self.item['revision']['evidence']['stored_material_audit']={'path':str(audit),'sha256':sha(audit)}
        identity={'asset_id':'fixture','model_sha256':self.item['revision']['model_sha256'],
                  'evidence':{key:value['sha256'] for key,value in self.item['revision']['evidence'].items()}}
        self.item['revision']['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.save({'without_packets':[{'id':'rebuilding'}]})
        decisions=self.root/'decisions.json';data=json.loads(decisions.read_text())
        data['decisions'].append({'asset_id':'rebuilding','scope':'geometry','decision':'approved',
                                 'exact_user_text':'Synthetic earlier approval','revision_sha256':'a'*64})
        decisions.write_text(json.dumps(data))
        self.assertEqual(prepare(self.manifest,'fixture',self.root/'output')['editable_pixels'],8)

    def test_exact_source_review_resolution_is_copied_to_preparation(self):
        handoff={'texture_issue':{'status':'correction-awaiting-user-review','generation_blocked':True}}
        handoff_path=self.root/'handoff.json';handoff_path.write_text(json.dumps(handoff))
        self.item['revision']['evidence']['handoff']={'path':str(handoff_path),'sha256':sha(handoff_path)}
        identity={'asset_id':'fixture','model_sha256':self.item['revision']['model_sha256'],
                  'evidence':{k:v['sha256'] for k,v in self.item['revision']['evidence'].items()}}
        self.item['revision']['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.save();record(self.manifest,['fixture'],'Synthetic corrected source packet approval')
        decision=json.loads((self.root/'decisions.json').read_text())['decisions'][-1]
        resolution={'asset_id':'fixture','revision_sha256':self.item['revision']['sha256'],
                    'approval_decision':decision,'handoff_sha256':sha(handoff_path),
                    'cleared_blockers':{'handoff.texture_issue':handoff['texture_issue']}}
        path=self.root/'source-review-resolutions.json'
        path.write_text(json.dumps({'version':1,'resolutions':[resolution]}))
        before=handoff_path.read_bytes();prepare(self.manifest,'fixture',self.root/'resolved')
        approval=json.loads((self.root/'resolved/approval.json').read_text())
        self.assertEqual(approval['source_review_resolution']['record'],resolution)
        self.assertEqual(sha(path),sha(self.root/'resolved/source-review-resolutions.json'))
        self.assertEqual(before,handoff_path.read_bytes())

    def test_changed_ownership_fails_before_creating_output(self):
        (self.packet/'views/view-0-known.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):prepare(self.manifest,'fixture',self.root/'blocked')
        self.assertFalse((self.root/'blocked').exists())


class SmallApprovedCanvas(PreparationTests):
    tile_size=(256,320)


class InvalidCanvas(unittest.TestCase):
    tile_size=(128,128)
    setUp=PreparationTests.setUp
    save=PreparationTests.save

    def test_reject_before_output(self):
        with self.assertRaisesRegex(ValueError,'custom-size'):
            prepare(self.manifest,'fixture',self.root/'blocked')
        self.assertFalse((self.root/'blocked').exists())



class EndpointPreparationTests(unittest.TestCase):
    tile_size=(256,320)
    setUp=PreparationTests.setUp
    save=PreparationTests.save

    def pair(self):
        import shutil
        applied=self.root/'applied';applied.mkdir();shutil.copytree(self.packet,applied/'modified')
        (applied/'model.blend').write_bytes(b'independently baked applied model')
        states=[]
        for state,workspace in [('initial',self.root),('applied',applied)]:
            record={'id':state,'workspace':str(workspace),'status':'ready-for-user','model_sha256':sha(workspace/'model.blend')}
            for field,relative in [('model','model.blend'),('solid','modified/solid.png'),('textured','modified/textured.png'),('frames','modified/views.json')]:
                path=workspace/relative;record[field]=str(path)
                self.item['revision']['evidence']['endpoint_'+state+'_'+field]={'path':str(path),'sha256':sha(path)}
            states.append(record)
        self.item['endpoint_reviews']=states
        identity={'asset_id':'fixture','model_sha256':self.item['revision']['model_sha256'],
                  'evidence':{k:v['sha256'] for k,v in self.item['revision']['evidence'].items()}}
        self.item['revision']['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.save()
        # Keep the pair's explicit revision approval; never approve a derived endpoint item.
        from record_approval import record as approve
        approve(self.manifest,['fixture'],'Approve both endpoint fixtures')
        return applied

    def test_applied_model_and_frames_keep_pair_approval(self):
        applied=self.pair();prepare(self.manifest,'fixture',self.root/'output',endpoint='applied')
        approval=json.loads((self.root/'output/approval.json').read_text())
        self.assertEqual(approval['geometry_revision'],self.item['revision']['sha256'])
        self.assertEqual(approval['saved_model_sha256'],sha(applied/'model.blend'))
        self.assertEqual(approval['endpoint_id'],'applied')
        self.assertEqual(set(approval['paired_model_sha256']),{'initial','applied'})

    def test_pair_requires_explicit_state_and_rejects_changed_sibling(self):
        applied=self.pair()
        with self.assertRaisesRegex(ValueError,'explicit endpoint'):prepare(self.manifest,'fixture',self.root/'missing')
        (applied/'model.blend').write_bytes(b'changed after pair approval')
        with self.assertRaises(ValueError):prepare(self.manifest,'fixture',self.root/'stale',endpoint='initial')
        self.assertFalse((self.root/'stale').exists())

    def test_nonpaired_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'paired review'):prepare(self.manifest,'fixture',self.root/'invalid',endpoint='applied')

class RevealedPreparationTests(unittest.TestCase):
    tile_size=(256,320)
    setUp=PreparationTests.setUp
    save=PreparationTests.save

    def reveal(self, bind=True):
        import shutil
        packet=self.root/'revealed';shutil.copytree(self.packet,packet)
        frames=json.loads((packet/'views.json').read_text())
        frames['object_names']=['room'];frames['render_object_names']=['room']
        (packet/'views.json').write_text(json.dumps(frames))
        for field in ('solid','textured'):
            path=packet/(field+'.png');self.item['revealed_'+field]=str(path)
            self.item['revision']['evidence']['revealed_'+field]={'path':str(path),'sha256':sha(path)}
        if bind:
            path=packet/'views.json'
            self.item['revision']['evidence']['revealed_frames']={'path':str(path),'sha256':sha(path)}
        identity={'asset_id':'fixture','model_sha256':self.item['revision']['model_sha256'],
                  'evidence':{k:v['sha256'] for k,v in self.item['revision']['evidence'].items()}}
        self.item['revision']['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.save();record(self.manifest,['fixture'],'Approve covered and revealed fixture')
        return packet

    def test_revealed_requires_bound_source_cameras(self):
        self.reveal(False)
        with self.assertRaisesRegex(ValueError,'manifest is absent'):
            prepare(self.manifest,'fixture',self.root/'blocked',revealed=True)
        self.assertFalse((self.root/'blocked').exists())

    def test_revealed_keeps_revision_and_exact_visibility(self):
        packet=self.reveal();prepare(self.manifest,'fixture',self.root/'output',revealed=True)
        frames=json.loads((self.root/'output/views.json').read_text())
        self.assertEqual(frames['render_object_names'],['room'])
        self.assertEqual(frames['texture_receiver_object_names'],['room'])
        self.assertEqual(frames['reviewed_manifest_sha256'],sha(packet/'views.json'))
        approval=json.loads((self.root/'output/approval.json').read_text())
        self.assertEqual(approval['geometry_revision'],self.item['revision']['sha256'])
        self.assertEqual(approval['review_state'],'revealed')

if __name__=='__main__':unittest.main()
