"""Restore conservative source-paving ownership without changing the courtyard mesh."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-castle-courtyard-ground'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def authority():
 from PIL import Image,ImageDraw
 # Measured on the covered source crop at origin (265,999). Conservative
 # margins exclude the hall, entry steps, roofs, tower drums and curtain caps.
 local=[[(107,292),(194,247),(241,248),(265,237),(288,248),(402,212),(403,180),(473,163),(513,164),(611,189),(672,204),(686,229),(650,238),(634,225),(603,211),(558,210),(516,220),(485,243),(471,267),(470,311),(455,352),(437,369),(286,362),(181,348),(83,344)],
 [(485,150),(502,134),(575,110),(601,91),(624,90),(635,101),(676,114),(698,109),(748,92),(779,108),(779,125),(740,126),(710,141),(685,162),(678,188),(618,181),(535,164)]]
 polygons=[[(x+265,y+999) for x,y in poly] for poly in local]
 target=WORK/'mask-review/inventory-courtyard-floor-v1';source=WORK/'mask-review/inventory-v11'
 if not target.exists():shutil.copytree(source,target)
 manifest=json.loads((source/'manifest.json').read_text());assert len(manifest['masks'])==543
 mask=Image.new('L',(2304,3520));draw=ImageDraw.Draw(mask)
 for poly in polygons:draw.polygon(poly,fill=255)
 mask.save(target/'000543.png')
 manifest['masks'].append(dict(index=543,layer=-1,layer_index=-1,png='000543.png',mask_type='authored-source-floor',box_top_left=[0,0],box_size=[2304,3520],obstacle_indices=[],source_sha256=sha(WORK/'source-states/covered.png'),source_polygons=polygons,limitation='Conservative visible paving only; foreground architecture and ambiguous edge pixels excluded. Source-camera first-hit gating additionally applies.'))
 manifest['source_native_inventory_sha256']=sha(source/'manifest.json');write(target/'manifest.json',manifest)
 d=json.loads((WORK/'mask-review/source-masks-v11-baseline.json').read_text());d['mask_inventory']=str(target/'manifest.json')
 a=d['projections']['exterior']['assignments'];row=next(a for a in a if a.get('source_node')=='building-366');row.update(mask_indices=[543],reviewed=True,constraint_kind='reviewed-authored-source-floor',native_ownership_reviewed=False,review_note='Visible source paving traced independently of geometry. Floor retained at native elevation100.001; runtime projection-area references do not prove painted ownership.')
 out=WORK/'mask-review/source-masks-courtyard-floor-v1.json';write(out,d)
 src=Image.open(WORK/'source-states/covered.png').convert('RGB');crop=(265,999,1274,1666);overlay=src.copy();overlay.paste(Image.blend(src,Image.new('RGB',src.size,(0,255,255)),.4),(0,0),mask);overlay.crop(crop).save(WORK/'castle-audit/courtyard-floor-source-ownership.png')
 write(WORK/'castle-audit/courtyard-floor-outline.json',{'source_sha256':sha(WORK/'source-states/covered.png'),'polygons':polygons,'elevation_unchanged':100.00101,'authority':str(out),'native_mask_preservation':all(sha(source/m['png'])==sha(target/m['png']) for m in manifest['masks'][:527])})
 return out
def finalize():
 w=WORK/'round-12/assets'/ASSET
 rgb=json.loads((w/'known-rgb-validation.json').read_text());validation=json.loads((w/'validation.json').read_text());views=json.loads((w/'modified/views.json').read_text())
 assert rgb['status']=='PASS' and validation['status']=='PASS' and len(views['views'])==8
 known=sum(v['counts']['source'] for v in views['views']);assert known>0
 assert rgb['packets'][0]['views_sha256']==sha(w/'modified/views.json')
 notes=['Retained the native 34-point contour and elevation100.001; concealed floor extends beneath foreground architecture.', 'Added independently traced conservative paving ownership; native masks are unchanged. All scene occluders participate in source-camera first-hit gating.', 'Inspected all eight solid and source-textured views. Every known pixel independently matches source RGB.']
 limitations=['Authored source-floor polygons are conservative, not native actor-occlusion evidence; small visible boundary strips remain unknown.', 'Concealed floor extent and thickness remain inherited; gray foreground areas are hidden beneath towers and curtain walls.']
 write(w/'candidate.json',dict(version=1,asset_id=ASSET,status='ready-for-user',geometry_reviewed=True,geometry_refined=False,inspected_views=list(range(8)),no_change_reason=notes[0],changes=notes,limitations=limitations,model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),recipe=str(Path(__file__).resolve()),known_source_pixels=known,source_texture_validation='known-rgb-validation.json',user_approval='pending',texture_generation='not-started'))
 (w/'review.md').write_text('# Castle courtyard floor\n\n'+'\n'.join('- '+n for n in notes+limitations)+'\n\nUser approval pending. No generated textures.\n')

if __name__=='__main__':
 if '--finalize' in sys.argv:finalize();sys.exit()
 if '--authority-only' in sys.argv:authority();sys.exit()
 sys.path.insert(0,str(Path(__file__).parent))
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/94116d984f92dbae')
 from render_slots import acquire
 acquire()
 w=WORK/'round-12/assets'/ASSET
 if not (w/'model.blend').exists():
  authority()
  from prepare_assets import main
  main(['--source-blend',str(WORK/'grouped/nottingham-grouped-v5.blend'),'--output',str(w.parent),'--source-path',str(WORK/'source-states/covered.png'),'--grouping-manifest',str(WORK/'grouping/catalog-v5.json'),'--inventory-path',str(WORK/'inventory/inventory-v2.json'),'--review-path',str(WORK/'grouping/grouping-review-v5.json'),'--projection-manifest',str(WORK/'state-review/baseline-final-layers.json'),'--source-mask-manifest',str(WORK/'mask-review/source-masks-courtyard-floor-v1.json'),'--width','256','--height','320','--prepare-only',ASSET])
 else:
  import bpy
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
 from refinement_workspace import modified
 modified(w)
