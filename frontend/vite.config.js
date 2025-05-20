import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  server: {
    proxy: {
      "/api": "http://localhost:8010",
      "/debug": "http://localhost:8010",
      "/config": "http://localhost:8010",
    },
  },
  plugins: [react()], // This should be an array with react plugin, not PostCSS config
  // Do not clean dist on build to preserve php folder and avoid permission issues
  build: {
    emptyOutDir: false,
  },
});

// Our backend routes are mounted under /api, so /api/query must be preserved.
// If we rewrite it to /query, FastAPI will 404.
// Our Vite proxy does exactly what we need: it passes /api/* through as-is to the backend on port 8010.
// Stripping /api only makes sense if the backend expects flat /query, which ours does not.
