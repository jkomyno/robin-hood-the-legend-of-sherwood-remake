"""Synthetic endpoint plan failures; never approves or stages production assets."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from endpoint_staging import validate_endpoint_plan
from review_evidence import sha

class EndpointPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.files={};self.endpoints=[];states={}
        for state,node,name in [('initial','building-001','raised'),('applied','building-002','lowered')]:
            w=self.root/state;w.mkdir();(w/'inspection/stored-materials').mkdir(parents=True)
            (w/'model.blend').write_text(state)
            (w/'workspace.json').write_text(json.dumps({'part_ids':['building-001','building-002'],'collection_name':'Fixture Working'}))
            (w/'inspection/stored-materials/audit.json').write_text(json.dumps({'objects':[{'object':name,'source_node':node}]}))
            for p in w.rglob('*'):
                if p.is_file():self.files[state+str(p.relative_to(w))]=p
            states[state]={'worker':str(w),'model_sha256':sha(w/'model.blend'),'source_nodes':[node],'active_component_names':[name],'default_hidden':state=='applied'}
            self.endpoints.append({'model_sha256':sha(w/'model.blend')})
        self.group={'asset_id':'fixture','states':states,'standalone_pivot':[1,2,3],'include_hidden_objects':['lowered'],'descriptor_states':{'active':'initial','initial':['building-001'],'applied':['building-002']}}
        self.item={'id':'fixture','revision':{'evidence':{k:{'path':str(p),'sha256':sha(p)} for k,p in self.files.items()}}}
        self.mapping=self.root/'mapping.json'
        self.mock=patch('endpoint_staging.endpoint_evidence',return_value=(self.endpoints,self.files,[]));self.mock.start();self.addCleanup(self.mock.stop)
    def run_plan(self,group=None,item=None):
        self.mapping.write_text(json.dumps({'version':1,'groups':[group or self.group]}))
        return validate_endpoint_plan(self.mapping,item or self.item,'Fixture')
    def test_bound_pair(self):
        p=self.run_plan();self.assertEqual(p['include_hidden_objects'],['lowered']);self.assertEqual(len(p['states']),2)
    def test_tampering(self):
        mutations=[lambda g:g['states']['applied'].update(model_sha256='0'*64),
                   lambda g:g['states']['applied'].update(active_component_names=['missing']),
                   lambda g:g['states']['applied'].update(active_component_names=['lowered','lowered']),
                   lambda g:g.update(include_hidden_objects=['raised']),
                   lambda g:g['states']['applied'].update(default_hidden=False),
                   lambda g:g.update(standalone_pivot=[1,float('nan'),3]),
                   lambda g:g['descriptor_states'].update(active='applied')]
        for mutate in mutations:
            g=copy.deepcopy(self.group);mutate(g)
            with self.subTest(group=g),self.assertRaises(ValueError):self.run_plan(g)
    def test_unbound_applied_artifact(self):
        item=copy.deepcopy(self.item);item['revision']['evidence']={k:v for k,v in item['revision']['evidence'].items() if not k.startswith('applied')}
        with self.assertRaisesRegex(ValueError,'not bound'):self.run_plan(item=item)
    def test_changed_bound_bytes(self):
        (self.root/'applied/model.blend').write_text('changed')
        with self.assertRaises(ValueError):self.run_plan()

if __name__=='__main__':unittest.main()
