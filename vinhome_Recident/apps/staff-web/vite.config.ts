import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/*
 * Development server and `vite preview` share one address and one proxy.
 *
 * The app talks to the business API under `/api/business`; the prefix is dropped on the way through,
 * as the production proxy does (see deploy/nginx). Which front door this server stands for
 * (`operations` or `field`) is sent as `X-Vinhomes-Surface`, because the API keeps one sign-in per
 * door.
 *
 *   APP_PORT          port to listen on                  (default 3020)
 *   VINHOMES_API_URL  where the business API runs        (default http://127.0.0.1:8000)
 *   VINHOMES_SURFACE  `operations` or `field`            (default: not sent)
 *   VINHOMES_API_ORIGIN  Origin sent to the API          (default: the browser's own)
 *                     Set it when the API only accepts the origins of its own deployment.
 */
const port = Number(process.env.APP_PORT) || 3020;
const surface = process.env.VINHOMES_SURFACE?.trim();
const apiOrigin = process.env.VINHOMES_API_ORIGIN?.trim();

const serving = {
  host: "127.0.0.1",
  port,
  strictPort: true,
  proxy: {
    "/api/business": {
      target: process.env.VINHOMES_API_URL || "http://127.0.0.1:8000",
      rewrite: (requestPath: string) =>
        requestPath.replace(/^\/api\/business/, ""),
      headers: {
        ...(surface ? { "X-Vinhomes-Surface": surface } : {}),
        ...(apiOrigin ? { Origin: apiOrigin } : {}),
      },
    },
  },
};

export default defineConfig({
  plugins: [tanstackRouter({ autoCodeSplitting: true }), react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: serving,
  preview: serving,
});
