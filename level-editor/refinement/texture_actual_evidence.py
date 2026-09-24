"""Resolve an explicitly reviewed actual-material sheet within its immutable bake."""
import hashlib
from pathlib import Path


def actual_sheet(bake, review):
    root = Path(bake).resolve()
    relative = Path(review.get('actual_sheet_path', 'actual/textured.png'))
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Actual sheet must be a confined relative bake path')
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Actual sheet escaped bake or is missing')
    digest = review.get('actual_sheet_sha256')
    if not digest or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Actual material sheet evidence changed')
    return path
