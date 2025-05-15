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
});
