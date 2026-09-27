# Lossy model quality investigation (2026-09-27)

The shared generator is `refinement/blender/lossy_assets.py`. It preserves triangle
counts, rebakes the published textures, encodes AVIF, and optionally quantizes
vertex attributes. The original `model.glb` remains the source of truth.

## Derby south gatehouse

The angle-based relaxation after Smart UV Project collapsed roof charts before
quantization. The old layout requested a 21,301-pixel atlas, hit the 4096 cap,
and achieved only 0.192 texels/map-pixel at the area-weighted median. Its lowest
decile was almost zero. Merely disabling quantization reproduced the black streaks:
mean image error was 12.172 with quantization and 12.167 without it.

Quantization also caused real damage: 66 tiny position triangles collapsed.
The new writer checks triangle area/orientation after rounding. Unsafe positions
remain float for the entire asset to preserve shared boundaries; unsafe UV
accessors remain float individually. Ordinary geometry still uses uint16.

The generator now keeps the projected charts, normalizes island scales, uses
eight-pixel minimum packing gutters, and extends baked edge texels for padding.
This avoids chart collapse and dark seams from adjacent-face gutter sampling.
Reducing padding to two pixels produced visible roof seams during verification.

Eight-view comparisons against the published source (640-pixel maximum render
edge, identical cameras) measured:

| Derby output | Mean max-channel error (0–255) | Worst-view p95 | GLB bytes |
| --- | ---: | ---: | ---: |
| Previous generator | 12.172 | 53 | 1,421,136 |
| Previous generator, no quantization | 12.167 | 53 | 1,943,988 |
| Fixed generator | 2.43 | 7 | 1,468,320 |

The fixed atlas remains 4096² and its density target is still capped by that
limit; the report records this. Validation is evidence, not a universal quality
threshold. Small occlusion-boundary differences can still have high peak errors.

## York versus Lincoln

The live receipts used identical generator settings. None of the inspected York,
Derby, or Lincoln base models used nearest filtering, so the separate nearest
density setting did not explain their differences.

York's unrefined projection-mapped models use a shared 8192² JPEG. That image size
does not describe an individual building's resolution: each building uses only a
small part of it. For example, `york-group-000` has a source area-weighted median
weakest-axis density of about 0.495 texels/map-pixel. Refined Lincoln assets have
separate surface textures around one texel/map-pixel (and Derby's gatehouse has
roughly 1.5–2). Some of the difference therefore exists in the published sources.

The old generator further capped each face's target by its *weakest* source
direction and sized the atlas to satisfy only the area-weighted median. This
discarded detail along better-sampled directions and left nearly half the surface
below target. It now uses the strongest source direction as the cap and targets
95% surface coverage (`--density-coverage`). York group 000 consequently changes
from a 320² atlas to 688², achieving about one texel/map-pixel. Upsampling cannot
recover details absent from the source artwork.

Higher coverage can increase atlas memory, particularly on refined assets with
many projected charts. The 4096 maximum and size/density reports remain in force.

## Verification and rebuilding

The lossy bookkeeping/precision tests and asset-index tests pass (26 tests).
Blender rendered eight source/output view pairs for Derby south gatehouse, York
group 000, and Lincoln south gatehouse. Local evidence and rollback backups are
under `work/lossy-quality-20260927/`; `gatehouse-comparison.png` shows source,
previous lossy, and fixed lossy. The three verified assets and their previews are
updated in the local library.

Receipts now include an explicit algorithm version. Other existing derivatives
are rebuilt on their next selected refresh; they are not silently considered
current because their old numeric settings happen to match. A full library
rebuild is separate from the three-asset validation:

```sh
blender --background --threads 2 --python-exit-code 1 \
  --python refinement/blender/lossy_assets.py -- library \
  --root library/3d-assets --run work/lossy-quality-full-rebuild --apply
```

Run from `level-editor`. Omit `--apply` for the plan, or add `--maps york derby
lincoln` to restrict the rebuild. Source models are never modified.
