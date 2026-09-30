import { defineConfig } from 'vite';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, sep } from 'node:path';

const DEFAULT_LOCAL_BINARIES_ROOT = fileURLToPath(
    new URL('../../../../binaries/', import.meta.url),
);
const LOCAL_BINARIES_ROOT = resolve(
    process.env.ROBIN_LOCAL_BINARIES_ROOT ?? DEFAULT_LOCAL_BINARIES_ROOT,
);
const ISOLATION_HEADERS = {
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
};

function contentType(path: string): string {
    if (path.endsWith('.json')) {
        return 'application/json';
    }
    if (path.endsWith('.js')) {
        return 'application/javascript';
    }
    if (path.endsWith('.wasm')) {
        return 'application/wasm';
    }
    return 'application/octet-stream';
}

// Match the production game document's isolation headers so local threaded
// runtimes can use shared wasm memory and sprite-decode workers. Runtime and
// datadir assets use the same origin through the routes below.
export default defineConfig({
    base: '/',
    publicDir: 'public',
    plugins: [{
        name: 'local-binaries-pages',
        configureServer(server) {
            server.middlewares.use((req, res, next) => {
                const pathname = req.url?.split('?', 1)[0] ?? '';
                // The shell has no favicon. Answer the browser's implicit
                // request explicitly instead of logging an asset-load error.
                if (pathname === '/favicon.ico') {
                    res.statusCode = 204;
                    res.end();
                    return;
                }
                if (!pathname.startsWith('/wasm/') && !pathname.startsWith('/datadirs/')) {
                    next();
                    return;
                }
                // These routes finish before Vite's own header middleware.
                // Worker scripts need COEP as well as the game document.
                for (const [name, value] of Object.entries(ISOLATION_HEADERS)) {
                    res.setHeader(name, value);
                }

                const decodedPath = decodeURIComponent(pathname);
                const filePath = resolve(LOCAL_BINARIES_ROOT, `.${decodedPath}`);
                if (!filePath.startsWith(`${LOCAL_BINARIES_ROOT}${sep}`)) {
                    res.statusCode = 403;
                    res.end('forbidden');
                    return;
                }
                if (!existsSync(filePath) || !statSync(filePath).isFile()) {
                    res.statusCode = 404;
                    res.end('not found');
                    return;
                }

                res.setHeader('content-type', contentType(filePath));
                createReadStream(filePath).pipe(res);
            });
        },
    }],
    // `'mpa'` disables Vite's HTML-fallback middleware so missing
    // static files return a real 404 instead of `index.html` with
    // status 200.  Keeps `fetch('./data/Data/datadir.bin')` from
    // resolving to HTML when the symlink is missing.
    appType: 'mpa',
    server: {
        headers: ISOLATION_HEADERS,
        // Vite's dev-mode FS protection refuses to follow symlinks
        // out of the project root by default, which breaks
        // `public/data` (a symlink to the converted shipping
        // datadir) and `pkg/robin.wasm` (the wasm-bindgen output
        // tree).  Allow the whole repo so symlinked artefacts
        // resolve from anywhere.
        fs: {
            allow: ['..', '../..', '../../..', '../../../..'],
        },
    },
    build: {
        target: 'es2022',
        sourcemap: false,
        rollupOptions: {
            input: {
                game: resolve(import.meta.dirname, 'index.html'),
                leaderboards: resolve(import.meta.dirname, 'leaderboards/index.html'),
            },
        },
    },
});
