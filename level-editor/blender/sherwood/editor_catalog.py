"""Explicit ownership of the pre-procedure Sherwood reconstruction.

Published IDs are derived from the descriptive names below. Display names
describe the source artwork; they do not claim new geometry approval.
"""
import re

NAMES = {
 0:'West camp hut roof',1:'West camp hut',5:'West camp barrel',6:'West camp tub',7:'Camp woodpile',
 8:'North camp hut walls',9:'North camp hut roof',10:'Camp supply shelter',
 11:'Camp worktable',12:'Camp dining table',14:'Camp preparation table',
 15:'West dining bench',16:'North dining bench',17:'East dining bench',18:'Preparation bench',
 19:'Camp wash stand',20:'Camp serving stool',21:'Camp barrel',22:'Camp baskets',23:'Round camp stool',
 24:'Ladder oak',25:'River oak',26:'West woodland tree',27:'Northwest woodland oak',28:'North woodland trunk',
 29:'West treehouse oak',30:'Central west treehouse oak',31:'Northwest woodland tree',32:'Central oak trunk',
 33:'Central oak buttress',34:'Leaning woodland tree',35:'West woodland oak',36:'Broad woodland oak',
 37:'East border oak',38:'East oak upper limb',39:'Woodland stump',40:'Spreading woodland oak',
 42:'Northeast woodland oak',44:'North border oak',45:'Northeast forked oak',46:'West border treehouse oak',
 47:'Riverbank rock',49:'Central oak treehouse',50:'West woodland branch',51:'West border woodland oak',
 52:'Central oak spreading root',53:'North woodland oak',54:'North border branch',55:'Northeast border oak',
 56:'Horizontal supply barrel',83:'Mossy riverbank outcrop',85:'West tree landing',86:'Ladder oak platform',
 88:'Central oak platform',89:'East oak platform',92:'Central tree landing',93:'West suspension bridge',
 94:'Long suspension bridge',95:'East suspension bridge',96:'East bridge landing',99:'West bridge landing',
 100:'West treehouse ladder',107:'Central treehouse thatch',108:'Central treehouse side roof',
 109:'North camp bed',110:'South camp bed',111:'River bluff',112:'Iron cooking cauldron',113:'Cooking stool',
 114:'Roasting spit',115:'Fallen camp branch',116:'Camp cut timber',117:'South river driftwood',118:'River driftwood',
 121:'Riverbank timber fence',122:'Treehouse baskets',123:'Hanging rope ladder',124:'Treehouse bucket',
 125:'West archery target',126:'East archery target',
}
NAMES.update({n:f'Riverbank boulder {n-56:02}' for n in range(57,83)})
PART_NAMES = {2:'Hut side wall',3:'Hut doorway',4:'Hut chimney',41:'Oak side limb',43:'Oak roots',48:'Central oak upper trunk',
 84:'Outcrop side',87:'Treehouse porch',90:'West border treehouse porch',91:'Platform extension',102:'Central treehouse walls',
 103:'Central treehouse roof',104:'Central west treehouse hut',105:'West treehouse hut',106:'West treehouse platform',119:'West border treehouse hut',120:'West border treehouse barrel'}


def source_node(collection, obj):
    """Resolve only explicit historical properties and recipe naming conventions."""
    name, props = obj['name'], obj['props']
    if name == 'Tree 036 upper traced limb': return 'building-038'
    if name == 'Central oak left buttress': return 'building-033'
    if name == 'Central oak left root': return 'building-052'
    source = props.get('source_obstacle')
    if source: return source
    if collection.startswith('10 '):
        owner = int(props['supporting_tree'])
        return f'building-{owner:03}' if owner >= 0 else 'foliage-foreground-oak'
    m = re.match(r'(?:Tree|Camp|Rock|Cooperage|Stool|Log pile|Bridge) (\d+)\b', name)
    if m: return f'building-{int(m[1]):03}'
    for prefix, node in [('Ladder oak',24),('Bridge 094',94),('Supply barrel',56),('Cooking cauldron',112),
                         ('Cooking spit',114),('Roast',114),('River fence',121),('River bluff',111),
                         ('Left treehouse ladder',100),('Central oak -',49),('Central hut - wall',102),
                         ('Central hut - roof',103),('Central hut - thatch',103),('Porch ',102),
                         ('Lower landing ',102),('Upper porch ladder',102),('Ring ladder',102)]:
        if name.startswith(prefix): return f'building-{node:03}'
    if name.startswith('Terrain -'): return 'ground'
    raise ValueError(f'Unmapped legacy mesh: {collection}: {name}')


def asset_type(name):
    if any(s in name.lower() for s in ('boulder','bluff','outcrop','rock')): return 'Terrain'
    if any(s in name.lower() for s in ('treehouse','hut','shelter')): return 'Building'
    if 'bridge' in name.lower(): return 'Bridge & gate'
    if 'fence' in name.lower(): return 'Wall'
    if any(s in name.lower() for s in ('oak','tree','trunk','branch','root','stump')): return 'Vegetation'
    return 'Prop'
