import { defineConfig } from "vite";
import solid from "@solidjs/vite-plugin";

// Separate production build of the actual editor with in-memory test fixtures.
export default defineConfig({
  // Match the application's direct listeners while Solid's delegated keys differ.
  plugins: [solid({ solid: { delegateEvents: false } })],
  publicDir: false,
  build: {
    target: "esnext",
    outDir: "dist/lifecycle",
    rollupOptions: { input: "tests/lifecycle.html" },
  },
  preview: { port: 5181 },
});
