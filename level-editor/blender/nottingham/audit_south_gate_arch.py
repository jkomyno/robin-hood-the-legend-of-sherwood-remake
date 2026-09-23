"""Reopen the gate packet and compare actual saved vertices with source targets."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from refine_south_gate_arch import CROWN,CORBELS,WORK


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--draw',action='store_true')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    args=parser.parse_args(argv);workspace=args.workspace.resolve()
    output=workspace/'inspection';output.mkdir(exist_ok=True)
    path=output/'saved-mesh-source-corners.json'
    if args.draw:
        draw(json.loads(path.read_text()),output)
        return
    from render_slots import acquire
    acquire(slots=2)
    import bpy
    report={'method':'Actual saved vertex indices correspond to recipe front profile corners; before nearest vertices are diagnostic only. Residuals test construction, not target choice.','snapshots':{}}
    for label,filename in [('before','baseline.blend'),('after','model.blend')]:
        blend=workspace/filename;bpy.ops.wm.open_mainfile(filepath=str(blend));bpy.context.view_layer.update()
        objects={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
        result={}
        for node,targets in [(205,CROWN),(213,CORBELS)]:
            obj=objects[f'building-{node:03}'];world=[obj.matrix_world@v.co for v in obj.data.vertices]
            projected=[[v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35))]for v in world]
            max_front=max(-v.y*math.sin(math.radians(35))for v in world)
            candidates=[i for i,v in enumerate(world)if abs(-v.y*math.sin(math.radians(35))-max_front)<.002]
            corners=[]
            for i,(x,y,role,visible) in enumerate(targets):
                if label=='after':
                    index=len(world)//2+i
                    assert index in candidates,(node,index)
                else:
                    index=min(candidates,key=lambda j:math.dist(projected[j],[x,y]))
                actual=projected[index]
                corners.append({'index':i,'mesh_vertex':index,'target':[x,y],'actual':actual,'visible':visible,'error':math.dist(actual,[x,y])})
            edges=[[projected[e.vertices[0]],projected[e.vertices[1]]]for e in obj.data.edges if all(v in candidates for v in e.vertices)]
            result[str(node)]={'corners':corners,'front_edges':edges}
        report['snapshots'][label]={'sha256':hashlib.sha256(blend.read_bytes()).hexdigest(),'nodes':result}
    assert max(c['error']for n in report['snapshots']['after']['nodes'].values()for c in n['corners'])<.002
    path.write_text(json.dumps(report,indent=2)+'\n')


def draw(report,output):
    from PIL import Image,ImageDraw
    source=Image.open(WORK/'source-states/covered.png').convert('RGB')
    for node,box,scale in [('205',(1238,2003,1440,2050),5),('213',(1278,2048,1395,2093),7)]:
        raw=source.crop(box);size=(raw.width*scale,raw.height*scale)
        canvas=Image.new('RGB',(size[0],(size[1]+28)*3),'#222222');d=ImageDraw.Draw(canvas)
        for row,label in enumerate(['source','before','after']):
            tile=raw.resize(size,Image.Resampling.NEAREST);td=ImageDraw.Draw(tile)
            def p(v):return ((v[0]-box[0])*scale,(v[1]-box[1])*scale)
            if label!='source':
                data=report['snapshots'][label]['nodes'][node]
                for edge in data['front_edges']:td.line([p(v)for v in edge],fill=(255,115,70)if label=='before'else(50,230,255),width=1)
                for c in data['corners']:
                    x,y=p(c['target']);a,b=p(c['actual'])
                    td.line((x,y,a,b),fill='magenta',width=1)
                    td.ellipse((x-2,y-2,x+2,y+2),fill='yellow'if c['visible']else'orange')
                    td.text((x+3,y-12 if c['index']%2 else y+3),str(c['index']),fill='white')
            offset=row*(size[1]+28);d.text((5,offset+5),f'{node}: {label}; actual saved front edges / numbered target corners',fill='white');canvas.paste(tile,(0,offset+28))
        canvas.save(output/f'{node}-actual-saved-edges.png')

if __name__=='__main__':main()
