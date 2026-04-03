/** Пусто = относительные пути `/api/...` (dev: Vite proxy; Netlify: rewrite на бэкенд). */
const raw = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return raw ? `${raw}${p}` : p;
}
