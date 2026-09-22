"""Build an immutable village ownership revision from reviewed native silhouettes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    root=Path('level-editor/work/leicester-refinement').resolve()
    source=root/'mask-audit/source-masks.json';contract=json.loads(source.read_text())
    inventory=(source.parent/contract['mask_inventory']).resolve()
    evidence=root/'round-1/village-inspection'
    corrections={}
    def assign(nodes,masks,exclude=(),reason='',evidence_id='VILLAGE-NATIVE-01'):
        for node in nodes:
            row={'source_node':f'building-{node:03}','mask_indices':list(masks),'reviewed':True,'evidence':evidence_id}
            if exclude:row.update(exclude_mask_indices=list(exclude),exclusions_reviewed=True,exclusion_reason=reason)
            corrections[row['source_node']]=row
    # Independently inspected full-size silhouettes and projected component wires.
    assign([16,17,18],[146],[147,154,155],'Trough, access pole and chimney have separate receivers.')
    assign([20],[152,153]);assign([21],[154],evidence_id='VILLAGE-POLE-02')
    assign([22],[151],[147,154],'Foreground trough and separate pegged access pole are not part of the curved attached roof.')
    assign([23],[155])
    assign([0,1,2],[106],evidence_id='VILLAGE-EAST-EDGE-08')
    assign([3,7],[128],[132,133,134],'Separate wheel, chimney and haypile must not project onto the main wall.')
    assign([4],[129,130]);assign([5],[134]);assign([6],[131]);assign([8],[133])
    assign([9,14],[119],[122,123,124,125],'Separate barrel, wheel, ladder and chimney artwork is excluded from main receivers.')
    assign([10],[121]);assign([11,12],[120]);assign([13],[122]);assign([15],[125])
    assign([64,65],[135],[137,138,139],'Woodpile, bucket and foreground cart/pile are independent source objects.')
    assign([66],[136]);assign([67],[137])
    # Mill-south: older semantic labels misidentified043 as roof and045 as pile.
    for nodes,masks in [([40],[160]),([41,42,43],[159]),([44],[161]),([45,46,47,56,58],[162]),([55],[168]),([57],[166]),([59],[169]),([60],[163]),([61],[165])]:
        assign(nodes,masks,[163,164,165,168,169] if nodes==[45,46,47,56,58] else (), 'Separate chimney, barrel, pail, woodpile and bench have distinct receivers.', 'VILLAGE-MILL-SOUTH-04')
    assign([77,78],[171],evidence_id='VILLAGE-MILL-STILT-05')
    assign([79,80],[170],[172,173,175], 'Wheel, chimney and flume railing have distinct receivers.', 'VILLAGE-MILL-STILT-05')
    assign([81],[174],[173],'Chimney has its own receiver.', 'VILLAGE-MILL-STILT-05')
    assign([82],[98],evidence_id='VILLAGE-MILL-STILT-05');assign([83],[173],evidence_id='VILLAGE-MILL-STILT-05')
    assign([84,85,86,87],[172],evidence_id='VILLAGE-MILL-STILT-05')
    assign([126],[185],[178,179,180,181,182,186,187,189,190], 'Rocky base excludes building, ladder, support timbers and separate small base blocks.', 'VILLAGE-STILT-WIRES-06')
    for node,mask in [(127,178),(128,178),(129,180),(130,186),(131,187),(132,190),(133,189),(134,182),(135,181),(136,185)]:
        assign([node],[mask],evidence_id='VILLAGE-STILT-WIRES-06')
    rows=contract['projections']['exterior']['assignments']
    rows=[r for r in rows if r.get('source_node') not in corrections]+list(corrections.values())
    contract['projections']['exterior']['assignments']=sorted(rows,key=lambda r:r.get('source_node',''))
    contract['mask_inventory']='inventory.json'
    a.output.mkdir(parents=True,exist_ok=False)
    inventory_data=json.loads(inventory.read_text())
    for record in inventory_data['masks']:
        if 'png' in record:record['png']=str((inventory.parent/record['png']).resolve(strict=True))
    (a.output/'inventory.json').write_text(json.dumps(inventory_data,indent=2)+'\n')
    manifest=a.output/'source-masks.json';manifest.write_text(json.dumps(contract,indent=2)+'\n')
    evidence_files={'VILLAGE-NATIVE-01':'native-village-details.png','VILLAGE-POLE-02':'pole154-grid.png','VILLAGE-SOUTH-03':'native-south-cottage-details.png','VILLAGE-MILL-SOUTH-04':'mill-south-component-wires.png','VILLAGE-MILL-STILT-05':'native-mill-stilt-details.png','VILLAGE-STILT-WIRES-06':'stilt-components.png','VILLAGE-MILL-WIRES-07':'mill-components.png','VILLAGE-EAST-EDGE-08':'east-edge-roof-ownership-diagnostic.png'}
    records=[]
    for key,name in evidence_files.items():
        path=evidence/name;shutil.copy2(path,a.output/name)
        records.append({'id':key,'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    stamp={'version':1,'status':'technical-ownership-reviewed','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'reviewer':'refine_village','evidence':records,'corrections':sorted(corrections),'findings':['Native16 is behind the east-edge house in the final source composite; positive106 owns the overlapping thatch, so16 must not be excluded from000/001/002.','Native154 is one pegged pole with nine visible crosspegs; previous two-rail ladder candidate is rejected.','Native silhouette and projected mesh wire comparison identifies040 roof,043 body,045 annex wall,055 woodpile.','This stamp approves source-pixel ownership only; geometry, open canopy reconstruction and all eight projected views still require separate inspection.'],'unresolved':['Watermill platform076 has no matching native silhouette; requires an independently traced bitmap. Stilt base126 geometry is still a coarse solid mass and support-frame geometry is missing.','Source silhouettes do not establish hidden depths or backside detail.']}
    (a.output/'technical-review.json').write_text(json.dumps(stamp,indent=2)+'\n')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from occlusion_constraints import SourceMaskConstraints
    import numpy as np
    from PIL import Image
    SourceMaskConstraints(manifest,'exterior',contract['projections']['exterior']['source_sha256'],(3136,1984),image_loader=lambda p:np.array(Image.open(p).convert('L'))>127)
    print(json.dumps({'manifest':str(manifest),'assignments':len(rows),'corrected_nodes':len(corrections),'validation':'PASS'}))
if __name__=='__main__':main()
