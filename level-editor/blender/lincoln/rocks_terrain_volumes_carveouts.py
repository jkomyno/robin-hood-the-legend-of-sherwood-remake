"""Ground-domain review choices for the rocks/terrain lane (pure data).

Domains are authored only for nodes whose painted surface has no (or too
little) native silhouette: plateau/terrace/road tops and slopes, the bridge
deck and parapets, the reject-all rock masses 434/435 and hillside volume
456. Rock nodes with reviewed native rock silhouettes keep those as the
authority: the first-hit pixels outside them are ground painted around the
rounded rock outline and must not be pulled onto the rock.

CARVEOUTS lists polygons (full-image covered.png pixels) of painted props or
structures with no native silhouette, found by inspecting each evidence sheet.
"""

MIN_PIXELS = 200
DOMAIN_NODES = {f'building-{n:03d}' for n in (52, 53, 54, 55, 56, 57, 61, 62, 63, 64, 65, 66, 67, 68, 70,
                                              74, 76, 434, 435, 456)}
SKIP_REASON = 'reviewed native rock silhouette is the receiver authority (first-hit pixels outside it are ground)'
CARVEOUTS = {
    'building-062': [{'polygon': [[1538, 1476], [1604, 1476], [1604, 1514], [1538, 1514]],
                      'what': 'painted sawhorse / timber trestle in front of the thatched cottage, no native mask'}],
    'building-067': [{'polygon': [[2688, 758], [2790, 758], [2790, 832], [2688, 832]],
                      'what': 'painted cart wheel, broken timber pile and barrel east of the north yard, '
                              'partly outside any native mask'}],
}


class _Skip(dict):
    def __contains__(self, node):
        return node not in DOMAIN_NODES

    def __getitem__(self, node):
        return SKIP_REASON


SKIP = _Skip()
