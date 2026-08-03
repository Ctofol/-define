import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const adminRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: adminRoot,
  base: "/admin/",
  plugins: [react()],
  build: {
    outDir: path.resolve(adminRoot, "../dist-admin"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/echarts") || id.includes("node_modules/zrender")) return "charts";
          if (id.includes("node_modules/antd") || id.includes("node_modules/@ant-design")) return "antd";
          if (id.includes("node_modules/react")) return "react";
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5174,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true }, "/media": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
