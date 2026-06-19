import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
export default defineConfig({
  base: "/dashboard/",
  publicDir: "../public",
  plugins: [vue()],
  server: {
    host: "localhost",
    port: 5174,
    strictPort: true,
    fs: {
      allow: [frontendRoot]
    }
  }
});
