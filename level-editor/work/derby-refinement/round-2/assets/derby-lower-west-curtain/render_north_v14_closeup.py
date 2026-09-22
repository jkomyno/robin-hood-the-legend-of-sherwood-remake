from pathlib import Path
root=Path(__file__).resolve().parent
exec(compile((root/'render_north_v7_closeup.py').read_text().replace('north-corner-v7','north-corner-v14'),str(root/'render_north_v7_closeup.py'),'exec'))
