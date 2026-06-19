import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const sharedRoot = fileURLToPath(new URL("../shared", import.meta.url));

export default defineConfig({
  publicDir: "../public",
  plugins: [vue()],
  resolve: {
    alias: {
      "@shared": sharedRoot
    }
  },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    fs: {
      allow: [frontendRoot]
    }
  }
});
