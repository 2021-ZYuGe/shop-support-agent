import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend always calls relative /api paths. During development Vite
// forwards them to FastAPI so cookies and CORS behave like a same-origin app.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
