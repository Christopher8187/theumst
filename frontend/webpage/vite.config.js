import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  publicDir: false,
  plugins: [vue()],
  resolve: {dedupe: ['vue']},
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: { '/images': process.env.PROXY_API_TARGET || process.env.VITE_API_BASE || 'http://localhost:8000' },
    fs: { allow: [frontendRoot] }
  }
});
