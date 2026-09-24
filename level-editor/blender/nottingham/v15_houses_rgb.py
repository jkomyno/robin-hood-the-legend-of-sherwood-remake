"""Verify source RGB against the exact source layer owning each ray receiver."""
import sys
from pathlib import Path
p=Path(__file__).with_name('verify_workspace_known_rgb.py')
s=p.read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')")
s=s.replace("for p in sources for im in [cache[p]]", "for d in data['projection_layers'] if owners[index].get('source_node') in d['receiver_nodes'] for im in [cache[str(Path(d['source_path']).resolve())]]")
exec(compile(s,str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})
