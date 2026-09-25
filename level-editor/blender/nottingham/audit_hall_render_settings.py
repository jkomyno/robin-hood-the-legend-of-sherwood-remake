"""Verify metadata finalization leaves all writable render settings unchanged."""
import sys,json,hashlib
from pathlib import Path
import bpy

def values(data):
    result={}
    for prop in data.bl_rna.properties:
        if prop.is_readonly or prop.identifier in {'name','name_full','rna_type'}:continue
        if prop.type not in {'BOOLEAN','INT','FLOAT','STRING','ENUM'}:continue
        value=getattr(data,prop.identifier)
        if getattr(prop,'is_array',False):value=list(value)
        elif isinstance(value,set):value=sorted(value)
        result[prop.identifier]=value
    return result

def nodes(tree):
    if tree is None:return None
    return dict(nodes=[dict(name=n.name,properties=values(n),defaults={s.identifier:list(s.default_value) if hasattr(s.default_value,'__len__') and not isinstance(s.default_value,str) else s.default_value for s in n.inputs if hasattr(s,'default_value') and (isinstance(s.default_value,(float,int,str,bool)) or type(s.default_value).__name__=='bpy_prop_array')}) for n in tree.nodes],links=[(l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in tree.links])

def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update()
    return dict(objects={o.name:dict(properties=values(o),matrix=[list(r) for r in o.matrix_world],data=o.data.name if o.data else None,modifiers=[dict(type=m.type,properties=values(m)) for m in o.modifiers]) for o in bpy.data.objects},materials={m.name:values(m) for m in bpy.data.materials},lights={l.name:dict(properties=values(l),nodes=nodes(l.node_tree)) for l in bpy.data.lights},cameras={c.name:values(c) for c in bpy.data.cameras},worlds={w.name:dict(properties=values(w),nodes=nodes(w.node_tree)) for w in bpy.data.worlds},scenes={s.name:dict(render=values(s.render),view=values(s.view_settings),display=values(s.display_settings),world=s.world.name if s.world else None) for s in bpy.data.scenes})

def main(before,after,out):
    a=json.loads(json.dumps(snapshot(before),default=list));b=json.loads(json.dumps(snapshot(after),default=list));differences=[key for key in a if a[key]!=b[key]]
    report=dict(status='PASS' if not differences else 'FAIL',before_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),after_sha256=hashlib.sha256(after.read_bytes()).hexdigest(),differences=differences,render_settings_sha256=hashlib.sha256(json.dumps(a,sort_keys=True,default=list).encode()).hexdigest(),counts={key:len(value) for key,value in a.items()})
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));assert not differences
if __name__=='__main__':
    a=sys.argv[sys.argv.index('--')+1:];main(*(Path(p).resolve() for p in a))
