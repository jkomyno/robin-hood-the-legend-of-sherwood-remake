"""Local source-pixel polyline editor. Serve a prepared project and save reviewed paths.

python3 level-editor/refinement/corner_editor.py path/to/project.json --port 5182
The project lists assets with image_path, crop [left,top,right,bottom], and paths.
Points always use full source-image coordinates, never display/crop coordinates.
"""
import argparse
import hashlib
import json
import math
import mimetypes
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def validate_paths(assets, originals):
    if not isinstance(assets, list) or len(assets) != len(originals):
        raise ValueError('Asset list changed')
    for asset, original in zip(assets, originals):
        if asset['id'] != original['id']:
            raise ValueError('Asset identity changed')
        paths = asset['paths']
        if not isinstance(paths, list) or len(paths) > 1000:
            raise ValueError('Invalid paths')
        ids = set()
        for path in paths:
            if not isinstance(path['id'], str) or path['id'] in ids:
                raise ValueError('Duplicate or invalid path ID')
            ids.add(path['id'])
            if not isinstance(path['name'], str) or len(path['name']) > 200:
                raise ValueError('Invalid name')
            if path.get('edge') not in ('front', 'rear', 'unspecified'):
                raise ValueError('Invalid edge role')
            if len(path['points']) > 10000:
                raise ValueError('Too many points')
            for point in path['points']:
                if len(point) != 2 or not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v < 100000 for v in point):
                    raise ValueError('Invalid source pixel')


def serve(project_path, port):
    project_path = Path(project_path).resolve()
    project = json.loads(project_path.read_text())
    output = project_path.parent / 'edited-corners.json'
    lock = threading.Lock()
    for asset in project['assets']:
        image = Path(asset['image_path']).resolve()
        asset['source_sha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
    revision = hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, mime='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

        def do_GET(self):
            route = urlsplit(self.path).path
            if route == '/api/project':
                with lock:
                    result = json.loads(json.dumps(project))
                    if output.exists():
                        saved = json.loads(output.read_text())
                        by_id = {a['id']: a for a in saved['assets']}
                        for a in result['assets']:
                            if a['id'] in by_id and by_id[a['id']]['source_sha256'] == a['source_sha256']:
                                a['paths'] = by_id[a['id']]['paths']
                    result.update(revision=revision, save_path=str(output))
                    self.respond(200, result)
            elif route == '/':
                self.respond(200, Path(__file__).with_name('corner-editor.html').read_bytes(), 'text/html; charset=utf-8')
            elif route.startswith('/images/') or route.startswith('/overlays/'):
                try:
                    index = int(route.rsplit('/', 1)[1])
                    if index < 0:
                        raise ValueError()
                    path = Path(project['assets'][index]['overlay_path' if route.startswith('/overlays/') else 'image_path'])
                    self.respond(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'image/png')
                except (ValueError, IndexError, KeyError):
                    self.respond(404, {'error': 'Unknown image'})
            else:
                self.respond(404, {'error': 'Not found'})

        def do_POST(self):
            nonlocal revision
            if self.path != '/api/save':
                return self.respond(404, {'error': 'Not found'})
            if self.headers.get('Origin') not in (f'http://localhost:{port}', f'http://127.0.0.1:{port}'):
                return self.respond(403, {'error': 'Use the local editor to save'})
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length < 4_000_000:
                    raise ValueError('Invalid request size')
                body = json.loads(self.rfile.read(length))
                validate_paths(body['assets'], project['assets'])
                with lock:
                    if body.get('revision') != revision:
                        return self.respond(409, {'error': 'Another tab saved changes. Download your JSON before reloading.'})
                    saved = dict(version=1, coordinate_system='full-source-image-pixels',
                                 saved_at=datetime.now(timezone.utc).isoformat(), assets=[])
                    for edited, original in zip(body['assets'], project['assets']):
                        saved['assets'].append({**original, 'paths': edited['paths']})
                    raw = (json.dumps(saved, indent=2) + '\n').encode()
                    if output.exists():
                        history = output.parent / 'corner-history'
                        history.mkdir(exist_ok=True)
                        (history / f'{revision}.json').write_bytes(output.read_bytes())
                    temporary = output.with_suffix('.tmp')
                    temporary.write_bytes(raw)
                    os.replace(temporary, output)
                    revision = hashlib.sha256(raw).hexdigest()
                    self.respond(200, {'revision': revision, 'path': str(output)})
            except (ValueError, KeyError, TypeError) as error:
                self.respond(400, {'error': str(error)})

    print(f'Battlement editor: http://localhost:{port}\nSaved points: {output}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--port', type=int, default=5182)
    args = parser.parse_args()
    serve(args.project, args.port)
