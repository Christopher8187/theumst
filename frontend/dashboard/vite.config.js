import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
export default defineConfig({
  base: "/dashboard/",
  publicDir: "../assets",
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
    fs: {
      allow: [frontendRoot]
    }
  }
});
