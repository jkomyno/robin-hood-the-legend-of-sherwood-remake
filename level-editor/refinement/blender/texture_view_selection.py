"""Explicit view selection policies for unknown texture texels."""
DEFAULT='near-tie-blend'
SINGLE='best-facing-single'
def policy(manifest):
    value=manifest.get('texture_view_selection',DEFAULT)
    if value not in (DEFAULT,SINGLE):raise ValueError('Unknown texture view selection: '+str(value))
    return value

def ordered(candidates,selection):
    if selection==DEFAULT:return sorted(candidates,key=lambda item:item[0],reverse=True)
    if selection!=SINGLE:raise ValueError('Unknown texture view selection')
    # Round only floating point noise in identical camera-facing directions.
    # Highest projected pixel density wins a tie; lower view index is stable.
    return sorted(candidates,key=lambda item:(round(item[0],6),item[1]['crop']['height']/item[1]['ortho_scale'],-item[1]['index']),reverse=True)

def eligible(accepted,remaining,score,best_scores,selection):
    return (~accepted & remaining) if selection==SINGLE else (~accepted & (score>=best_scores-.12))
