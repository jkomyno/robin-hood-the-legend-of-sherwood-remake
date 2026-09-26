import { openHttpLibrary, downloadMap } from '../src/http-library';
import { readJson, writeText, listFiles } from '../src/fs';
import { createNewMap } from '../src/new-map';

/** Real OPFS, with HTTP responses isolated from the published library. */
export async function checkHttpLibrary() {
  const root = await navigator.storage.getDirectory();
  const storage = await root.getDirectoryHandle('http-library-test', {create:true});
  const originalFetch = window.fetch;
  const originalPicker = window.showDirectoryPicker;
  const remote = new Map([
    ['/library/3d-assets/index.json', JSON.stringify({version:1, assets:[]})],
    ['/library/scenes/index.json', JSON.stringify(['York.level3d.json'])],
    ['/library/scenes/York.level3d.json', JSON.stringify({map:'York', revision:'published'})],
    ['/library/3d-assets/york/tower/model.glb', 'model bytes'],
  ]);
  const assert = (value: unknown, message: string) => { if (!value) throw new Error(message); };
  window.showDirectoryPicker = async () => { throw new Error('HTTP library requested a filesystem picker'); };
  window.fetch = async (url, options) => {
    assert(!options?.method || options.method === 'GET', 'HTTP library attempted a write');
    const data = remote.get(String(url));
    return new Response(data ?? '', {status:data === undefined ? 404 : 200});
  };
  try {
    let library = (await openHttpLibrary('/library/', storage)).handle;
    let maps = await library.getDirectoryHandle('scenes');
    assert((await readJson<{revision:string}>(maps, 'York.level3d.json')).revision === 'published', 'Published map did not load');
    await writeText(maps, 'York.level3d.json', JSON.stringify({map:'York', revision:'edited'}));
    library = (await openHttpLibrary('/library/', storage)).handle;
    maps = await library.getDirectoryHandle('scenes');
    assert((await readJson<{revision:string}>(maps, 'York.level3d.json')).revision === 'edited', 'Browser save did not survive reopening');
    assert(JSON.parse(remote.get('/library/scenes/York.level3d.json')!).revision === 'published', 'Published map changed');
    await createNewMap(library, 'New forest');
    assert((await listFiles(maps)).sort().join(',') === 'New forest.level3d.json,York.level3d.json', 'Published and local maps did not merge');
    let rejected = false;
    try { await createNewMap(library, 'York'); } catch { rejected = true; }
    assert(rejected, 'New map overwrote published map');
    const assetDir = await (await (await library.getDirectoryHandle('3d-assets')).getDirectoryHandle('york')).getDirectoryHandle('tower');
    assert(await (await (await assetDir.getFileHandle('model.glb')).getFile()).text() === 'model bytes', 'Nested HTTP asset did not load');
    rejected = false;
    try { await assetDir.getFileHandle('model.glb', {create:true}); } catch { rejected = true; }
    assert(rejected, 'Asset write was allowed');
    const document = await readJson(maps, 'New forest.level3d.json');
    let exported: Promise<unknown> | undefined;
    const click = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
      assert(this.download === 'New forest.level3d.json', 'Download filename changed');
      exported = originalFetch(this.href).then(response => response.json());
    };
    try { downloadMap('New forest', document); } finally { HTMLAnchorElement.prototype.click = click; }
    assert(JSON.stringify(await exported) === JSON.stringify(document), 'Downloaded map differs from saved map');
  } finally {
    window.fetch = originalFetch;
    window.showDirectoryPicker = originalPicker;
    await root.removeEntry('http-library-test', {recursive:true});
  }
}
