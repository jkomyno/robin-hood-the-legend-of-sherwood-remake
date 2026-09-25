# Lincoln refinement

Implements `level-editor/refinement/PROCEDURE.md` for Lincoln. Run from the repository
root; evidence lives in `level-editor/work/lincoln-refinement/` (resume from `RESUME.json`).

1. `source_states.py`: covered/revealed artwork, native masks and patch-state frames → `source-states/`.
2. `setup_scene.py` (Blender) freezes the volume export into `baseline/lincoln-baseline.blend`
   and writes the inventory. `--annotate-states` records patch membership; `--illustrate` renders crops.
   All 466 native obstacles are present. The exporter's `terrace-N` names are normalized to `building-N`.
3. `grouping/build_catalog.py` + `validate_review.py` (Blender): reviewed canonical catalog, 96 groups.
4. `calibrate_source_sun.py`: artwork shadow landmarks → `lighting-calibration/map-lighting.json`.
   Packets pass it explicitly (`prepare_assets.py --lighting`); Derby's default is never used.
5. `mask-review/build_manifest.py`: reviewed exterior receivers (`source-masks-v1.json`).
6. `group_scene.py` (Blender) applies the catalog → `grouped/lincoln-grouped-v1.blend`.
   It renames `Lincoln …` scene/collections to `lincoln …`, because shared helpers derive
   `<catalog map> Working`.
7. `prepare_assets.py` (Blender) creates frozen per-asset workspaces in `round-1/assets/`.
8. Lane workers follow `work/lincoln-refinement/WORKER_BRIEF.md` with `refine_<lane>.py` recipes.
9. `build_gallery.py` collects packets into the pending-only review gallery. It requires a
   hash-bound `source-coverage-audit.json` for every ready card.

10. Publication (staging never touches the live library):
    - `publish_stage.py` (Blender) takes a hash-bound plan (e.g. `publication-1/stage-v1.plan.json`):
      grouped baseline plus the approved models that differ from it. It writes `worker.blend`, the
      staged catalog and `integration.json`.
    - `verify_publication_scene.py` checks every approved model against the staged worker.
    - `publish_export.py` exports the full map (component splits become
      `building-NNN--component-<name>` parts), the standalone assets and `publication-metadata.json`.
      Freeze its tooling into the publication directory with `freeze_tooling.py --output`.
    - Then run `verify_publication_assets.py`, `verify_staged_handoffs.py` (with
      `effective-plan.json`), `pipeline/src/prepare-publication-document.ts` (first
      `lincoln.level3d.json`), `prepare_publication_browser.py --document` with
      `browser/verify_publication.mjs`, and finally `promote_staged_publication.py`.
    - A texture republish is a new plan whose imports name the approved baked workers.

`freeze_tooling.py` pins shared helpers in `tooling/<id>`, and `render_slots.py` limits
concurrent Blender renders to three.

Map-wide finding: native obstacles extrude from z = 0, but the castle plateau is at native
z = 220. Every castle object must be reseated on its real ground contact.
