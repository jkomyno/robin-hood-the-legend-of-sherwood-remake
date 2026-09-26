"""Run the level-editor Python tests: plain ones with python3, bpy ones in background Blender.

    python3 level-editor/refinement/run_tests.py            # everything
    python3 level-editor/refinement/run_tests.py --no-blender
    python3 level-editor/refinement/run_tests.py -k lossy   # substring filter on paths

Collects ``test_*.py`` under refinement/, refinement/blender/ and blender/<map>/.
A test needs Blender when it, or a local module it imports at top level, imports
bpy, bmesh or mathutils. unittest modules without a ``__main__`` guard run through
``python3 -m unittest``. ``*_selftest.py`` integration runs are opt-in (--selftests)
because they write under level-editor/work/.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

EDITOR = Path(__file__).resolve().parents[1]
ROOTS = [EDITOR / 'refinement', EDITOR / 'refinement/blender', EDITOR / 'blender']
BLENDER_MODULES = {'bpy', 'bmesh', 'mathutils'}


def collect(selftests):
    patterns = ['test_*.py'] + (['*_selftest.py'] if selftests else [])
    found = set()
    for root in ROOTS:
        for pattern in patterns:
            glob = root.rglob(pattern) if root.name == 'blender' and root.parent == EDITOR else root.glob(pattern)
            found.update(path for path in glob if '__pycache__' not in path.parts)
    return sorted(found)


def _tree(path):
    try:
        return ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return None


def _top_level_imports(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split('.')[0])
    return names


def needs_blender(path, seen=None):
    seen = set() if seen is None else seen
    if path in seen:
        return False
    seen.add(path)
    tree = _tree(path)
    if tree is None:
        return False
    names = _top_level_imports(tree)
    if names & BLENDER_MODULES:
        return True
    search = [path.parent, EDITOR / 'refinement/blender', EDITOR / 'refinement']
    for name in names:
        local = next((directory / f'{name}.py' for directory in search if (directory / f'{name}.py').is_file()), None)
        if local is not None and needs_blender(local, seen):
            return True
    return False


def command(path, blender):
    if blender:
        return [blender, '--background', '--factory-startup', '--threads', '2',
                '--python-exit-code', '1', '--python', str(path)]
    tree = _tree(path)
    guarded = tree is not None and any(isinstance(node, ast.If) and '__main__' in ast.unparse(node.test)
                                       for node in tree.body)
    return [sys.executable, path.name] if guarded else [sys.executable, '-m', 'unittest', path.stem]


def run(path, blender, timeout):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    started = time.monotonic()
    try:
        result = subprocess.run(command(path, blender), cwd=path.parent, env=env, capture_output=True,
                                text=True, timeout=timeout)
        code, output = result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired as error:
        code, output = 'timeout', f'{error}'
    return path, code, output, time.monotonic() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-k', dest='filter', help='only run tests whose path contains this substring')
    parser.add_argument('-j', dest='jobs', type=int, default=4, help='parallel plain-Python tests (default 4)')
    parser.add_argument('--blender-jobs', type=int, default=2, help='parallel Blender tests (default 2)')
    parser.add_argument('--no-blender', action='store_true', help='skip tests that need Blender')
    parser.add_argument('--selftests', action='store_true', help='also run *_selftest.py integration runs')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('-v', '--verbose', action='store_true', help='print output of passing tests too')
    args = parser.parse_args()
    blender = shutil.which('blender')
    tests = [path for path in collect(args.selftests) if not args.filter or args.filter in str(path)]
    plain = [path for path in tests if not needs_blender(path)]
    bpy_tests = [path for path in tests if path not in plain]
    skipped = bpy_tests if args.no_blender or not blender else []
    if skipped and not args.no_blender:
        print(f'blender not found on PATH; skipping {len(skipped)} Blender tests', flush=True)
    results = []
    with ThreadPoolExecutor(max(1, args.jobs)) as pool:
        results += pool.map(lambda path: run(path, None, args.timeout), plain)
    if not skipped:
        with ThreadPoolExecutor(max(1, args.blender_jobs)) as pool:
            results += pool.map(lambda path: run(path, blender, args.timeout), bpy_tests)
    failures = [(path, code, output) for path, code, output, _ in results if code != 0]
    for path, code, output, seconds in results:
        status = 'ok' if code == 0 else f'FAIL ({code})'
        print(f'{status:10} {seconds:6.1f}s  {path.relative_to(EDITOR)}')
        if code != 0 or args.verbose:
            print('\n'.join('    ' + line for line in output.strip().splitlines()[-40:]))
    print(f'\n{len(results) - len(failures)} passed, {len(failures)} failed, {len(skipped)} skipped '
          f'({len(plain)} plain, {len(bpy_tests)} Blender)')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
