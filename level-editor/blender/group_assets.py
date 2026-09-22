"""Compatibility entry point; implementation lives in refinement/blender."""
from pathlib import Path as _Path
import sys as _sys
_target = _Path(__file__).resolve().parents[1] / "refinement" / "blender" / "group_assets.py"
_sys.path.insert(0, str(_target.parent))
__file__ = str(_target)
exec(compile(_target.read_text(), __file__, "exec"), globals())
