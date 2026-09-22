from pathlib import Path
root=Path(__file__).resolve().parent
code=(root/'render_north_v6.py').read_text().replace('north-corner-v6','north-corner-v10')
exec(compile(code,str(root/'render_north_v6.py'),'exec'))
