"""The published reveal records retain state without embedding source artwork."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_editor import reveal_metadata


with tempfile.TemporaryDirectory() as directory:
    manifest = Path(directory) / "layers.json"
    manifest.write_text(json.dumps({
        "map": "Derby",
        "patches": [{
            "id": "patch-001", "name": "Opened room", "coverage_candidates": [],
            "sight_before": [], "sight_after": [], "state": {"active": False},
            "graphic": {"image": "missing-cover.png", "bbox": [1, 2, 3, 4]},
        }],
        "mission_patches": [{
            "id": "mission-patch-001", "sight_before": [], "sight_after": [],
            "projection_sources": {"initial": "missing-composite.png"},
            "states": {"initial": {"frames": [{
                "image": "missing-frame.png", "bbox": [5, 6, 7, 8],
                "delay": 2, "sound_id": 3,
            }]}},
        }],
    }))
    result = reveal_metadata({"reveal_manifest_path": str(manifest)}, [], include_all=True)
    assert result["patches"][0]["graphic"] == {"bbox_source_pixels": [1, 2, 3, 4]}
    assert result["mission_patches"][0]["states"]["initial"]["frames"] == [
        {"bbox": [5, 6, 7, 8], "delay": 2, "sound_id": 3},
    ]
    assert "projection_sources" not in result["mission_patches"][0]
    assert "mission_graphics" not in result
    assert "image" not in json.dumps(result)

print("Reveal metadata excludes source artwork and retains patch state")
