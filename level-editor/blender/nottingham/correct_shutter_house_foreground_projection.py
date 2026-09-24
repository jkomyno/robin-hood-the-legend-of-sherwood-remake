"""Remove proven foreground contamination from an immutable shutter-house copy.

The remaining grazing-side projection requires independent geometry review;
this recipe does not fabricate an approval or mark the asset ready.
"""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from render_slots import acquire
 from freeze_tooling import select_tooling
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import prepare,modified
 from correct_source_projection import geometry
 old=WORK/'round-1/assets/nottingham-southeast-shutter-house'
 out=WORK/'round-29/assets/nottingham-southeast-shutter-house'
 if out.exists():raise RuntimeError('Use a new immutable workspace for another revision')
 c=json.loads((old/'workspace.json').read_text());m=json.loads((old/'source-masks.json').read_text())
 row=next(a for a in m['projections']['exterior']['assignments']if a['source_node']=='building-036')
 row.update(mask_indices=[37],exclude_mask_indices=[32,33,40],exclusions_reviewed=True,exclusion_reason='Native40 is the separate ivy-covered garden return; native32 and33 are the neighboring timber house and roof. Their source pixels must not stretch across the shutter-house grazing side wall.',review_evidence=str(WORK/'coordinator-audit/shutter-stripe/native-source.png'),review_note='Native37 contains the house facade but includes foreground overlap. Exact neighboring native silhouettes are subtracted; mesh geometry is retained.')
 mask=WORK/'coordinator-audit/shutter-stripe/corrected-masks.json';mask.write_text(json.dumps(m,indent=2)+'\n')
 bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));before=geometry()
 prepare(out,asset_id=c['asset_id'],scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=mask,width=c['width'],height=c['height'],context_padding=c['context_padding'],framing_padding=c.get('framing_padding',1.04))
 modified(out);assert before==geometry(),'Geometry changed'
 report=dict(version=1,status='awaiting-independent-review',asset_id=c['asset_id'],previous_workspace=str(old),previous_model_sha256=sha(old/'model.blend'),model_sha256=sha(out/'model.blend'),modified_views_sha256=sha(out/'modified/views.json'),geometry_unchanged=True,corrected_nodes=['building-036'],recipe=str(Path(__file__).resolve()),recipe_sha256=sha(__file__),approval='pending',diagnosis='Grazing side wall received foreground garden-return pixels through an overly broad native-mask union; foreground overlap also occurs within native37. Native32/33/40 subtraction rejects only proven foreign source artwork.')
 (out/'foreground-projection-correction.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
