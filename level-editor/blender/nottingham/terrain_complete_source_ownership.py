"""Author background ownership from native scenery and reviewed structural exclusions."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
# These source-space polygons enclose scenery that is absent from the native
# silhouette union. Their purpose is exclusion, never attribution to terrain.
STRUCTURES={
 'southern cart shafts':[(1770,3440),(1874,3445),(1873,3487),(1770,3487)],
 'southwest prison wall seam':[(233,1800),(249,1800),(249,1942),(233,1942)],
 'small hut yard tools':[(438,2864),(472,2858),(485,2865),(480,2888),(457,2900),(442,2893)],
 'small hut rear fence':[(433,2789),(483,2783),(486,2827),(434,2829)],
 'low barn table and sawhorse':[(1045,2980),(1118,2980),(1118,3032),(1045,3032)],
 'mill yard branches and axe':[(1540,2737),(1562,2747),(1577,2770),(1610,2781),(1638,2790),(1638,2830),(1609,2838),(1560,2823),(1540,2790)],
 'eastern timber bridge and railing':[(1898,2718),(1934,2688),(2030,2756),(2022,2783),(1957,2758),(1927,2739)],
 'mill stream fence':[(1910,2954),(1943,2926),(1991,2901),(1997,2887),(2028,2912),(2020,2935),(2007,2933),(1963,2952),(1958,2966),(1930,2974),(1910,2981)],
 'village leaning fence and planks':[(852,2458),(877,2472),(897,2459),(907,2504),(898,2588),(856,2568),(856,2538),(851,2533),(865,2499),(852,2491)],
 'southeast annex ladder':[(1837,1879),(1873,1879),(1873,1964),(1837,1964)],
 'town stair support ends':[(1705,1972),(1745,1972),(1746,2010),(1705,2010)],
 'town post foot':[(1815,1975),(1835,1975),(1835,2010),(1815,2010)],
 'raised castle courtyard and entrance':[(285,1070),(1170,1070),(1170,1545),(285,1545)],
 'western bridge deck':[(422,2962),(632,2872),(661,2894),(445,2981)],
 'main bridge deck':[(1333,3064),(1645,3121),(1640,3166),(1332,3099)],
 'northeast timber fence':[(2034,523),(2098,507),(2098,534),(2040,550)],
 'western churchyard tall cross':[(1712,646),(1737,646),(1737,705),(1712,705)],
 'western churchyard foreground cross':[(1742,697),(1773,707),(1773,735),(1742,724)],
 'church threshold steps':[(1730,1029),(1810,1065),(1804,1087),(1779,1089),(1717,1061),(1717,1044)],
 'eastern churchyard grave enclosure':[(2207,711),(2255,742),(2253,752),(2210,738)],
 'eastern churchyard upper grave slab':[(2280,731),(2304,730),(2304,752),(2280,747)],
 'eastern churchyard lower grave slab':[(2280,763),(2304,762),(2304,803),(2278,803)],
 'eastern churchyard tomb and iron fence':[(2180,1051),(2221,1045),(2258,1071),(2258,1109),(2180,1084)],
}

STRUCTURES.update({'wooden bridge full deck edge': [[1918, 2723], [1945, 2710], [1968, 2729], [1987, 2740], [2004, 2752], [2027, 2768], [2024, 2777], [2011, 2787], [1970, 2768], [1954, 2758], [1943, 2752], [1927, 2741]], 'stream fence left post': [[1932, 2968], [1938, 2968], [1937, 3003], [1932, 3003]], 'stream fence middle post': [[1953, 2941], [1959, 2941], [1959, 2979], [1952, 2981]], 'stream fence upper post': [[1974, 2917], [1980, 2916], [1981, 2960], [1974, 2962]], 'stream fence descending main rail': [[1935, 2976], [1976, 2937], [2009, 2918], [2012, 2921], [1979, 2941], [1936, 2981]], 'stream fence lower diagonal': [[1936, 2985], [1978, 2945], [2007, 2928], [2010, 2932], [1981, 2950], [1936, 2990]], 'stream fence lower return rail': [[1956, 2969], [1983, 2963], [1985, 2967], [1956, 2973]], 'churchyard raised grave front and sides': [[2208, 738], [2225, 727], [2251, 747], [2251, 760], [2235, 769], [2208, 748]], 'churchyard tomb fence feet': [[2180, 1075], [2194, 1059], [2205, 1059], [2213, 1070], [2245, 1070], [2252, 1077], [2252, 1094], [2241, 1109], [2225, 1110], [2212, 1103], [2200, 1100], [2192, 1091], [2180, 1096]]})

STRUCTURES.update({'small wooden grave cross': [[2218, 783], [2235, 793], [2234, 796], [2229, 793], [2231, 809], [2228, 810], [2226, 791], [2217, 785]], 'eastern grave slab front': [[2284, 746], [2303, 743], [2303, 752], [2293, 758], [2285, 752]], 'small wooden cross upper stem': [[2224, 784], [2229, 784], [2230, 797], [2226, 794]]})

def main():
 output=WORK/'mask-review/inventory-terrain-complete-v7'
 if output.exists():raise FileExistsError(output)
 output.mkdir()
 parent=WORK/'mask-review/source-masks-v11-baseline.json';manifest=json.loads(parent.read_text());ip=(parent.parent/manifest['mask_inventory']).resolve();inventory=json.loads(ip.read_text());srcpath=WORK/'source-states/covered.png';source=Image.open(srcpath).convert('RGB');excluded=Image.new('L',source.size);evidence=[];seen=set()
 def add(path,origin,reason):
  key=(str(path.resolve()),tuple(origin))
  if key in seen:return
  seen.add(key);layer=Image.new('L',source.size);layer.paste(Image.open(path).convert('L'),tuple(origin))
  nonlocal excluded
  excluded=ImageChops.lighter(excluded,layer);evidence.append(dict(path=str(path.resolve()),sha256=sha(path),origin=origin,reason=reason))
 for row in inventory['masks']:
  if row['index']<527:add(ip.parent/row['png'],row['box_top_left'],f"native scenery {row['index']}")
 gallery=WORK/'mask-review/inventory-terrain-complete-v1/candidate-input.json';frozen=json.loads(gallery.read_text())
 (output/'candidate-input.json').write_text(json.dumps(frozen,indent=2)+'\n')
 for item in frozen['items']:
  if item['id']=='nottingham-terrain-ground':continue
  workspace=Path(item['workspace']);maskfile=workspace/'source-masks.json'
  if not maskfile.exists():continue
  masks=json.loads(maskfile.read_text());invpath=Path(masks['mask_inventory']);invpath=invpath if invpath.is_absolute() else maskfile.parent/invpath;rows={r['index']:r for r in json.loads(invpath.read_text())['masks']};nodes=set(json.loads((workspace/'workspace.json').read_text())['part_ids'])
  for assignment in masks['projections']['exterior']['assignments']:
   if assignment['source_node'] not in nodes:continue
   for index in assignment['mask_indices']:
    if index<527:continue
    row=rows[index];add(invpath.parent/row['png'],row['box_top_left'],item['id'])
 drawn=Image.new('L',source.size);draw=ImageDraw.Draw(drawn)
 for polygon in STRUCTURES.values():draw.polygon(polygon,fill=255)
 excluded=ImageChops.lighter(excluded,drawn);accepted=ImageChops.invert(excluded);accepted.save(output/'ground-source-domain.png');drawn.save(output/'explicit-nonterrain.png');excluded.save(output/'all-scenery-exclusions.png')
 for row in inventory['masks']:row['png']=str((ip.parent/row['png']).resolve())
 index=max(r['index'] for r in inventory['masks'])+1
 inventory['masks'].append(dict(index=index,layer='authored-terrain-complete',layer_index=0,png=str((output/'ground-source-domain.png').resolve()),mask_type='reviewed-ground',box_top_left=[0,0],box_size=list(source.size),obstacle_indices=[],character_polyline=None,projectile_polyline=None))
 (output/'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n');manifest['mask_inventory']=str(output/'manifest.json');manifest['projections']['exterior']['assignments']=[a for a in manifest['projections']['exterior']['assignments'] if a['source_node']!='ground'];manifest['projections']['exterior']['assignments'].append(dict(source_node='ground',mask_indices=[index],reviewed=True,constraint_kind='complete-background-minus-native-and-reviewed-scenery',review_note='Observed background terrain and water artwork; all native scenery, reviewed custom asset masks and explicitly traced nonterrain structures excluded. Unknown beneath scenery remains neutral.'))
 rules=[]
 for a in manifest['projections']['exterior']['assignments']:
  if a['source_node']=='ground':continue
  rules.append(dict(reviewed=True,source_node=a['source_node'],receiver_nodes=['ground'],mask_indices=a['mask_indices'],reason='The independently reviewed complete ground domain excludes every native and reviewed scenery silhouette. Foreign collision-proxy overshoot outside its source silhouette must not erase source-visible ground.',review_evidence=str(output/'authoring.json')))
 manifest['projections']['exterior']['occluder_constraints']=rules
 (output/'source-masks.json').write_text(json.dumps(manifest,indent=2)+'\n');preview=Image.new('RGB',source.size,(70,70,70));preview.paste(source,mask=accepted);preview.save(output/'source-ownership.png');(output/'authoring.json').write_text(json.dumps(dict(source_sha256=sha(srcpath),mask_sha256=sha(output/'ground-source-domain.png'),accepted_pixels=sum(1 for p in accepted.get_flattened_data() if p>127),structural_exclusions=STRUCTURES,mask_inputs=evidence,method='Every native scenery silhouette and current owned authored mask is excluded, then separately observed nonterrain source structures are excluded. Independent visual inspection is required; a native-mask complement is not itself semantic ownership proof.'),indent=2)+'\n');print(output)
if __name__=='__main__':main()
