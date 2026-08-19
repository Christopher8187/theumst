import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  base: "/demo/",
  publicDir: false,
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5175,
    strictPort: true,
    fs: { allow: [frontendRoot] }
  }
});
