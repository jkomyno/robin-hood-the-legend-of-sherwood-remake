// Prepare a private local Full-game corpus and the URL layout used by Vite.
// This does not publish assets or build the runtime. All generated files stay
// below the explicitly selected output; the converter export is input-only.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { constants } from 'node:fs';
import { copyFile, mkdir, readFile, symlink, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { parseWebContentManifest, verifyDatadirCorpus } from './verify-datadir-corpus.mjs';
import { stageCloudflareHeaders } from './stage-cloudflare-headers.mjs';
const [sourceArg, outputArg, extra] = process.argv.slice(2);
if (!sourceArg || !outputArg || extra !== undefined) {
    throw new Error('usage: node wasm-www/scripts/prepare-local-full.mjs CONVERTER_OUTPUT ABSENT_OUTPUT');
}
const source = resolve(sourceArg), output = resolve(outputArg);
if (output.startsWith(`${source}/`)) throw new Error('output must be outside the converter output');
const bytes = await readFile(join(source, 'Data/robinhood-web-content.json'));
const manifest = parseWebContentManifest(bytes, 'local Full export', 'full');
const digest = createHash('sha256').update(bytes).digest('hex');
const engineCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: new URL('../..', import.meta.url), encoding: 'utf8',
}).trim();
if (!/^[0-9a-f]{40}$/u.test(engineCommit)) throw new Error('local runtime requires a full source commit');
const short = engineCommit.slice(0, 12);
await mkdir(output); // Refuse to mix this run with earlier output.
const corpus = join(output, 'corpus');
const base = join(corpus, 'datadirs/full', digest);
await mkdir(base, { recursive: true });
await writeFile(join(base, 'robinhood-web-content.json'), bytes, { flag: 'wx' });
for (const file of [manifest.datadir, ...manifest.files]) {
    const input = join(source, 'Data', file.path);
    const destination = join(base, file.path);
    await mkdir(dirname(destination), { recursive: true });
    if (file === manifest.datadir && file.byte_length > 25 * 1024 * 1024) {
        const data = await readFile(input);
        for (let offset = 0, part = 0; offset < data.length; offset += 24 * 1024 * 1024, part++) {
            await writeFile(`${destination}.part${part}`, data.subarray(offset, offset + 24 * 1024 * 1024), { flag: 'wx' });
        }
    } else {
        await copyFile(input, destination, constants.COPYFILE_EXCL);
    }
}
const bindings = join(corpus, 'datadirs/replays/v2');
await mkdir(bindings, { recursive: true });
await writeFile(join(bindings, `${short}.json`), JSON.stringify({
    url: `/datadirs/full/${digest}/datadir.bin`,
    sha256: manifest.datadir.sha256,
    byteLength: manifest.datadir.byte_length,
}), { flag: 'wx' });
await stageCloudflareHeaders('datadir', corpus);
// Full-only local corpus: no historical production Demo generations are present.
const verified = await verifyDatadirCorpus(corpus, { requireCurrent: false });
await mkdir(join(output, 'runtime/wasm', short), { recursive: true });
await writeFile(join(output, 'runtime/wasm/latest.json'), JSON.stringify({ commit: engineCommit, short }), { flag: 'wx' });
await mkdir(join(output, 'serve'));
await symlink(join(output, 'runtime/wasm'), join(output, 'serve/wasm'));
await symlink(join(corpus, 'datadirs'), join(output, 'serve/datadirs'));
const receipt = { source, output, engineCommit, short, contentEngineCommit: manifest.engine_version,
    contentManifestSha256: digest, assetCount: verified.assetCount, totalBytes: String(verified.totalBytes) };
await writeFile(join(output, 'receipt.json'), JSON.stringify(receipt, null, 2), { flag: 'wx' });
console.log(JSON.stringify(receipt, null, 2));
