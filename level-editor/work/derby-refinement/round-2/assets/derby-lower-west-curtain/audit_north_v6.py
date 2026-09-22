"""Saved-mesh audit with newly inspected return cap endpoints."""
from pathlib import Path
root=Path(__file__).resolve().parent
code=(root/'render_mesh_edge_evidence.py').read_text()
code=code.replace("root/'inspection/complete-wall-candidate-v5'/label", "root/'inspection/north-corner-v6'/label")
code=code.replace("sin,cos=math.sin", """observations=[r for r in observations if '025' not in r['id'] or 'return' not in r['id']]
observations.append({'id':'north-025-return-cap-endpoints','points':[[338,1736],[341,1728],[349,1718],[354,1708],[363,1697],[367,1690],[372,1682],[376,1675]]})
sin,cos=math.sin""")
code=code.replace("[('building-025',(310,1525,412,1770)),('building-023',(315,1795,393,1985)),('building-042',(385,2110,527,2250))]", "[('building-025',(310,1525,412,1770))]")
exec(compile(code,str(root/'render_mesh_edge_evidence.py'),'exec'))
