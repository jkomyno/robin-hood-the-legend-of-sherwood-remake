"""Draw source-camera crown edges without altering frozen review packets.

These wire overlays expose measured repeat counts and phase. They intentionally
show every crown edge, including edges occluded by foreground artwork; they
are inspection supplements, not substitutes for masked eight-view rendering.
"""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refine_castle_secondary_details import WORK, upper_wall, east_curtain, west_crown, gate_crown, watchtower_crown


def main():
    native_path = WORK / 'baseline/nottingham.rhp.json'
    native = json.loads(native_path.read_text())['sight_obstacles']
    source_path = WORK / 'round-1/assets/nottingham-castle-upper-wall/reference/source.png'
    source = Image.open(source_path)
    output = WORK / 'castle-secondary-audit'
    specs = [
        ('watchtower-crown', (565,195,795,350), 830, [watchtower_crown(native,536)[:2]]),
        ('watchtower-upper-crown', (660,85,770,170), 905, [watchtower_crown(native,n)[:2] for n in [538,539]]),
        ('upper-crown', (725, 795, 1110, 948), 260, [upper_wall(native,n)[:2] for n in [360,365]]),
        ('upper-landing-crown', (640, 995, 790, 1080), 180, [upper_wall(native,367)[:2]]),
        ('east-crown', (1100,680,1330,1280), 260, [east_curtain(native)[:2]]),
        ('west-crown', (175,1130,805,1410), 260, [west_crown(native[328]['points'])[:2]]),
        ('gate-west-crown', (745,1200,898,1320), 330, [gate_crown(native,n)[:2] for n in [331,332]]),
    ]
    reports=[]
    for name,box,minimum_z,objects in specs:
        image=source.crop(box).convert('RGBA')
        draw=ImageDraw.Draw(image)
        total=0
        for vertices,faces in objects:
            edges=set()
            for face in faces:
                for a,b in zip(face,face[1:]+face[:1]):
                    if min(vertices[a][2],vertices[b][2])<minimum_z:
                        continue
                    edge=tuple(sorted((a,b)))
                    if edge in edges:
                        continue
                    edges.add(edge)
                    draw.line([(vertices[i][0]-box[0],vertices[i][1]-vertices[i][2]-box[1]) for i in edge],
                              fill=(0,255,255,255),width=1)
            total+=len(edges)
        path=output/(name+'-candidate-wire.png')
        image.resize((image.width*3,image.height*3),Image.Resampling.NEAREST).save(path)
        reports.append({'file':str(path),'source_crop':box,'drawn_edges':total,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (output/'secondary-crown-wire-evidence.json').write_text(json.dumps({
        'version':1,'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'native_source_sha256':hashlib.sha256(native_path.read_bytes()).hexdigest(),
        'recipe_sha256':hashlib.sha256((Path(__file__).parent/'refine_castle_secondary_details.py').read_bytes()).hexdigest(),
        'inspection_only':True,'visibility_note':'Wire edges behind source foreground objects remain visible in these supplements.',
        'images':reports},indent=2)+'\n')


if __name__=='__main__':
    main()
