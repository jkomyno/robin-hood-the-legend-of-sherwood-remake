import { isNotFound } from './fs.ts';

const missing = (path: string) => new DOMException(`Missing library file: ${path}`, 'NotFoundError');
function segment(name: string) {
  if (!name || name === '.' || name === '..' || /[\\/\0]/.test(name)) throw new Error('Invalid library path');
  return name;
}

/** Read-only HTTP assets with browser-local map documents layered over published maps. */
export async function openHttpLibrary(base = '/library/', storage?: FileSystemDirectoryHandle) {
  const response = await fetch(base+'3d-assets/index.json', {cache:'no-store'});
  if (!response.ok) throw new Error(`Cannot load library catalog (${response.status})`);
  const catalog = await response.json();
  if (!catalog || !Array.isArray(catalog.assets)) throw new Error('Invalid asset library index');
  const browser = storage ?? await navigator.storage.getDirectory();
  const workspace = await browser.getDirectoryHandle('sherwood-level-editor', {create:true});
  const maps = await workspace.getDirectoryHandle('maps', {create:true});
  const remoteFile = async (path: string) => {
    const result = await fetch(base+path.split('/').map(encodeURIComponent).join('/'), {cache:'no-cache'});
    if (result.status === 404) throw missing(path);
    if (!result.ok) throw new Error(`Cannot read ${path} (${result.status})`);
    return new File([await result.arrayBuffer()], path.split('/').at(-1)!, {type:result.headers.get('content-type') ?? ''});
  };
  function directory(prefix: string): FileSystemDirectoryHandle {
    const isMaps = prefix === 'scenes/';
    return {
      kind:'directory', name:prefix ? prefix.split('/').at(-2)! : 'HTTP library',
      async getDirectoryHandle(name: string) {
        const next = prefix+segment(name)+'/';
        return directory(next);
      },
      async getFileHandle(name: string, options?: FileSystemGetFileOptions) {
        const path = prefix+segment(name);
        if (isMaps && name.endsWith('.level3d.json')) {
          try { return await maps.getFileHandle(name, options); }
          catch (error) { if (!isNotFound(error)) throw error; }
          const file = await remoteFile(path);
          return {kind:'file', name, getFile:async() => file,
            async createWritable() { return (await maps.getFileHandle(name,{create:true})).createWritable(); }} as FileSystemFileHandle;
        }
        if (options?.create) throw new DOMException('Library assets are read-only', 'NotAllowedError');
        const file = await remoteFile(path);
        return {kind:'file',name,getFile:async() => file} as FileSystemFileHandle;
      },
      async *entries() {
        const names = new Map<string,'file'|'directory'>();
        if (!isMaps) throw new Error('Only map enumeration is supported; use the asset index for assets');
        const published: unknown = JSON.parse(await (await remoteFile('scenes/index.json')).text());
        if (!Array.isArray(published) || published.some(name => typeof name !== 'string' || !name.endsWith('.level3d.json')))
          throw new Error('Invalid map index');
        for (const name of published) names.set(segment(name), 'file');
        if (isMaps) for await (const [name,entry] of maps.entries()) if (entry.kind==='file' && name.endsWith('.level3d.json')) names.set(name,'file');
        for (const [name,kind] of names) yield [name,kind==='directory'?directory(prefix+name+'/'):{kind,name}] as [string,FileSystemHandle];
      },
      async removeEntry(name: string) {
        if (!isMaps || !segment(name).endsWith('.level3d.json')) throw new DOMException('Library assets are read-only','NotAllowedError');
        await maps.removeEntry(name);
      },
    } as unknown as FileSystemDirectoryHandle;
  }
  return {handle:directory('')};
}

export function downloadMap(name: string, document: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(document,null,2)+'\n'], {type:'application/json'}));
  const link = window.document.createElement('a'); link.href=url; link.download=name+'.level3d.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url),0);
}
