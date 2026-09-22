# East Hall recovery handoff

The current source-alignment candidate is `next-zigzag-v3/recovery-review/model.blend`.
Its authority projection and 48 degree sunlight sheets are beside it in `modified/`.
The report `next-zigzag-v3/review.md` embeds 33 existing images inside its own `images/` directory.

This is not approved for publication or texture synthesis. The rear parapet mesh has 127 boundary edges versus 37 at the casement baseline. The southwest parapet has one boundary edge and six nonmanifold edges. Lower facades remain intact, and all 768 protected meshes are unchanged. The east corner is closed again after recovering the previously unpropagated foreground seam correction.

The 118 recorded source points distinguish observed corners from inferred hidden caps. Foreground residuals use nearest projected mesh edges, without visibility filtering, and are not independent evidence that the artist's intended corners were identified correctly. Rear and stair residuals use the rendered upper silhouette. The stair/roof junction still has a 5.83 pixel residual.

Recovery sequence:

1. Load `next-zigzag-v3/front-runs-trial.blend`, the newer foreground weld/T-junction correction saved after the earlier packets.
2. Execute `rebuild_rear_visible.py`, then `refine_stair_turret_trace.py` in Blender.
3. Execute `repair_trace_seams.py` on `traced-runs-candidate.blend`. This saves `repaired-candidate.blend`; it only welds serialization-scale seams and collinear edge intersections.
4. Execute `reproject_front_trial.py -- recovery-review` on `repaired-candidate.blend`. The output directory must not already exist. This validates the accepted native-mask checkpoint, reapplies layered ownership projection and writes model plus eight views.
5. Execute `validate_traced_candidate.py -- <absolute repaired-candidate.blend path>` to verify the actual candidate against the casement baseline.
6. Execute `inspect_walltop_exact.py -- candidate-edges.json`, then the ordinary Python scripts `draw_front_comparison.py`, `measure_trace_residuals.py` and `build_trace_report.py`.

`cap_upper_seams.py` is an unpromoted experiment. Its `seam-cap-test.blend` closes 14 upper loops and reduces rear boundary edges to 71, but does not close the remaining transition between the source-fitted parapet footprint and retained lower wall footprint. Do not replace the review candidate with that experiment without inspecting and reprojecting it.

Next geometry task: rebuild that rear join as a continuous transition at z=376, closing the end cuts at x=1359 and x=1567 while preserving lower wall surfaces and the traced cap silhouette. The new cap strip and retained body have different footprints; a generic fill-holes operation is insufficient. Separately eliminate the southwest wall's overlapping seam faces at z=365. Then rerun validation and a new projection/review directory before asking for final approval.

Blender MCP was unavailable at localhost:9876 during recovery. All work used deterministic background Blender processes with two threads.
