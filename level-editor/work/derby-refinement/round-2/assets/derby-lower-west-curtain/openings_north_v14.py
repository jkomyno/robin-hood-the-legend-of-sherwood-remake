from pathlib import Path
root=Path(__file__).resolve().parent
exec(compile((root/'openings_north_v12.py').read_text().replace('north-corner-v12','north-corner-v14'),str(root/'openings_north_v12.py'),'exec'))
