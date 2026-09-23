"""Independently compare known pixels in each audited castle packet to source."""
import sys
from pathlib import Path
path=Path(__file__).with_name('verify_workspace_known_rgb.py')
source=path.read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')")
for rd,name in [(28,'watchtower'),(4,'southeast-spire'),(1,'northwest-spire'),(27,'northeast-spire'),(5,'southwest-stair')]:
 w=Path(__file__).resolve().parents[3]/f'level-editor/work/nottingham-refinement/round-{rd}/assets/nottingham-castle-{name}'
 sys.argv=[str(path),'--',str(w)];exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
