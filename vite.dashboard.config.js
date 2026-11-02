import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL("./dashboard", import.meta.url)),
  server: { host: "0.0.0.0", port: 5180, strictPort: true },
  preview: { host: "0.0.0.0", port: 5181, strictPort: true },
  build: { outDir: "../dist-dashboard", emptyOutDir: true },
});
