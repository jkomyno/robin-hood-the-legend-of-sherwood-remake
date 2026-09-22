from pathlib import Path
root=Path(__file__).resolve().parent
code=(root/'render_north_v7_closeup.py').read_text().replace('north-corner-v7','north-corner-v10')
exec(compile(code,str(root/'render_north_v7_closeup.py'),'exec'))
