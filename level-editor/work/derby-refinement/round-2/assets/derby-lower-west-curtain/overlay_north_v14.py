from pathlib import Path
root=Path(__file__).resolve().parent
exec(compile((root/'overlay_north_v10.py').read_text().replace('north-corner-v10','north-corner-v14').replace('v10','v14').replace('(322,1550,392,1664)','(322,1550,404,1664)'),str(root/'overlay_north_v10.py'),'exec'))
