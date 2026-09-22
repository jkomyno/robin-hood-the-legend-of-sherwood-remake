from pathlib import Path
root=Path(__file__).resolve().parent
exec(compile((root/'verify_north_v13.py').read_text().replace('north-corner-v13','north-corner-v14'),str(root/'verify_north_v13.py'),'exec'))
