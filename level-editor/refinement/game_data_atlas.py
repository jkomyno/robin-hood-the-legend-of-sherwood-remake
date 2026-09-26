"""Lossless, deterministic sprite-bank atlases with pixel-identical frame deduplication."""
import hashlib
from io import BytesIO
from PIL import Image


def pack_atlas(paths):
    images, identities, unique = [], {}, {}
    for path in dict.fromkeys(paths):
        with Image.open(path) as source:
            image = source.convert('RGBA')
        key = (image.size, hashlib.sha256(image.tobytes()).digest())
        if key not in unique:
            unique[key] = len(images)
            images.append(image)
        identities[path] = unique[key]
    if not images:
        raise ValueError('Cannot pack an empty sprite bank')
    # Tallest-first shelves; try several widths and keep the smallest occupied area.
    order = sorted(range(len(images)), key=lambda i: (-images[i].height, -images[i].width, i))
    candidates = []
    for width in (128, 256, 512, 1024, 2048, 4096):
        if max(image.width + 2 for image in images) > width:
            continue
        shelves, rects, used_width = [], {}, 0
        for i in order:
            image = images[i]
            w, h = image.width + 2, image.height + 2
            shelf = next((s for s in shelves if s[2] >= h and s[0] + w <= width), None)
            if shelf is None:
                shelf = [0, sum(s[2] for s in shelves), h]
                shelves.append(shelf)
            rects[i] = [shelf[0] + 1, shelf[1] + 1, image.width, image.height]
            shelf[0] += w
            used_width = max(used_width, shelf[0])
        height = sum(s[2] for s in shelves)
        if height <= 4096:
            candidates.append((used_width * height, max(used_width, height), used_width, height, rects))
    if not candidates:
        raise ValueError('Sprite bank does not fit in a single 4096px atlas')
    _, _, width, height, rects = min(candidates, key=lambda c: c[:4])
    atlas = Image.new('RGBA', (width, height))
    for i, image in enumerate(images):
        x, y, _, _ = rects[i]
        # No alpha mask: preserve semi-transparent shadow pixels and hidden RGB exactly.
        atlas.paste(image, (x, y))
    output = BytesIO()
    # exact=True also preserves RGB under fully transparent pixels.
    atlas.save(output, format='WEBP', lossless=True, exact=True, method=6)
    return output.getvalue(), {path: rects[i] for path, i in identities.items()}
