"""Narrow exceptions for approved continuous foliage rims and sidedness."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from foliage_texture_bake import authored_volume_seam, facing_score

uv=np.array([[0.,0.],[1.,0.],[1.,0.]])
volume={'foliage_recipe':'leicester-continuous-forest-volume-v8'}
assert authored_volume_seam(volume,uv)
assert not authored_volume_seam({'foliage_recipe':'leicester-foliage-lobes-v5'},uv)
assert not authored_volume_seam(volume,np.zeros((3,2)))
assert not authored_volume_seam(volume,np.array([[0.,0.],[.5,0.],[1.,0.]]))
assert facing_score({'foliage_card_sides':'double-sided'},-.8)==.8
assert facing_score({'foliage_card_sides':'paired-one-sided'},-.8)==-.8
assert facing_score({},-.8)==-.8
print('FOLIAGE SAMPLER RULES PASS')
