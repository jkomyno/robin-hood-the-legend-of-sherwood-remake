"""Run the existing source-pixel auditor on the new exact review cameras."""
from pathlib import Path
W=Path(__file__).resolve().parent
source=(W/'audit.py').read_text()
source=source.replace("W/'modified/views.json'", "W/'trace-v2/modified/views.json'")
source=source.replace("W/f'modified/views/", "W/f'trace-v2/modified/views/")
source=source.replace("W/'ownership-audit.json'", "W/'trace-v2/ownership-audit.json'")
exec(compile(source,str(W/'audit.py'),'exec'),{'__file__':str(W/'audit.py'),'__name__':'__main__'})
