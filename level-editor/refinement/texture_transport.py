"""Validate an exact, unscaled content crop of a padded generation response."""
from pathlib import Path
from PIL import Image


def validate_crop(raw, content, preserved, padding):
    raw, content, preserved = (Path(p).resolve(strict=True) for p in (raw, content, preserved))
    if raw.parent != content.parent or raw.parent != preserved.parent:
        raise ValueError('Transport content must belong to the same generation')
    if not isinstance(padding, dict):
        raise ValueError('Explicit transport padding evidence required')
    box = padding.get('content_box', {})
    with Image.open(raw) as r, Image.open(preserved) as p, Image.open(content) as c:
        if (padding.get('version') != 1 or padding.get('kind') != 'bottom-padding' or
                r.size != (padding.get('width'), padding.get('height')) or
                p.width != r.width or not 0 < p.height < r.height or
                (box.get('left'), box.get('top')) != (0, 0) or
                (box.get('width'), box.get('height')) != p.size or c.size != p.size):
            raise ValueError('Unproven generation transport geometry')
        if c.convert('RGBA').tobytes() != r.crop((0, 0, *p.size)).convert('RGBA').tobytes():
            raise ValueError('Transport content differs from exact unscaled raw crop')
