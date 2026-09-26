"""Small evidence helpers shared by recipes: hashing, JSON records, recipe copies.

Pure Python (no bpy). Recipes that already define their own ``sha``/``digest``
keep them; new code should import these instead of adding another copy.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha(path):
    """SHA-256 of a file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    """SHA-256 of a JSON value in canonical form (sorted keys, no whitespace)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    """Write indented JSON atomically (temporary file in the same directory, then rename)."""
    path = Path(path)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)
    return path


def record_recipe(workspace, recipe):
    """Copy a geometry recipe into ``workspace/recipe/`` and return its candidate fields.

    Gallery builders re-hash ``candidate.json["recipe"]`` on every rebuild. A
    workspace-relative copy keeps that evidence valid when the live script is
    later edited, moved or deleted. An existing copy must be byte-identical.
    """
    workspace, recipe = Path(workspace).resolve(strict=True), Path(recipe).resolve(strict=True)
    target = workspace / 'recipe' / recipe.name
    if target.exists():
        if sha(target) != sha(recipe):
            raise ValueError(f'Workspace already holds a different {target.name}; use a new workspace revision')
    else:
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(recipe, target)
    return {'recipe': str(target.relative_to(workspace)), 'recipe_sha256': sha(target)}
