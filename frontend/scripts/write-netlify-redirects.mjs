/**
 * Перед `vite build` пишет `public/_redirects` для Netlify:
 * - при NETLIFY_API_ORIGIN — прокси /api/* на бэкенд (один origin в браузере);
 * - всегда SPA fallback.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "..", "public");
const origin = (process.env.NETLIFY_API_ORIGIN ?? "").trim().replace(/\/$/, "");

const lines = [];
if (origin) {
  lines.push(`/api/*  ${origin}/api/:splat  200`);
}
lines.push("/*  /index.html  200");

fs.mkdirSync(publicDir, { recursive: true });
fs.writeFileSync(path.join(publicDir, "_redirects"), `${lines.join("\n")}\n`, "utf8");
process.stdout.write(`[netlify-redirects] wrote public/_redirects (${lines.length} rules, api proxy: ${Boolean(origin)})\n`);
