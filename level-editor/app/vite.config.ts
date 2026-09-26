import { defineConfig } from "vite";
import solid from "vite-plugin-solid";
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [solid()],
  publicDir: '.library-public',
  server: { port: 5180, fs:{allow:[fileURLToPath(new URL('../../',import.meta.url))]} },
  build: { target: "esnext", copyPublicDir: false },
});
