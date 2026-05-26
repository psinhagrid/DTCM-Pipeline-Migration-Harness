// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... } }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
// @cloudflare/vite-plugin builds from this — wrangler.jsonc main alone is insufficient.
export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      port: 8080,
      proxy: {
        "/api":       { target: "http://localhost:8001", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
        "/stream":    { target: "http://localhost:8001", changeOrigin: true, ws: true },
        "/run":       { target: "http://localhost:8001", changeOrigin: true },
        "/pipelines": { target: "http://localhost:8001", changeOrigin: true },
        "/result":    { target: "http://localhost:8001", changeOrigin: true },
        "/conversion":{ target: "http://localhost:8001", changeOrigin: true },
        "/reconcile":  { target: "http://localhost:8001", changeOrigin: true },
        "/deployment": { target: "http://localhost:8001", changeOrigin: true },
        "/output":     { target: "http://localhost:8001", changeOrigin: true },
        "/reset":      { target: "http://localhost:8001", changeOrigin: true },
        "/graph":           { target: "http://localhost:8001", changeOrigin: true },
        "/skills-api":      { target: "http://localhost:8001", changeOrigin: true },
        "/user-input":      { target: "http://localhost:8001", changeOrigin: true },
        "/pending-input":   { target: "http://localhost:8001", changeOrigin: true },
        "/migration-plan":  { target: "http://localhost:8001", changeOrigin: true },
      },
    },
  },
});
