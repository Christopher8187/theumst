import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig(({ mode }) => ({
  base: "/dashboard/",
  publicDir: false,
  plugins: [vue()],
  resolve: { dedupe: ["vue"] },
  server: {
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
    proxy: {
      "/images": { target: process.env.PROXY_API_TARGET || loadEnv(mode, process.cwd(), "VITE_").VITE_API_BASE || "http://localhost:8000", changeOrigin: true }
    },
    fs: { allow: [frontendRoot] }
  }
}));
