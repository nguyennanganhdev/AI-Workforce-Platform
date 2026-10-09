import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const proxy = {
  "/api/business": { target: process.env.VINHOMES_API_URL || "http://127.0.0.1:8000", rewrite: (path: string) => path.replace(/^\/api\/business/, ""),
    // As the deployed front does: the API keeps a resident's sign-in apart from the staff apps'.
    // VINHOMES_API_ORIGIN: the Origin to send when the API only accepts the origins of its own deployment.
    headers: { "X-Vinhomes-Surface": "resident", ...(process.env.VINHOMES_API_ORIGIN ? { Origin: process.env.VINHOMES_API_ORIGIN } : {}) } },
};
export default defineConfig({ plugins: [react()], server: { proxy }, preview: { proxy } });
