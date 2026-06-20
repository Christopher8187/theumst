const LOCAL_API_BASE = "http://localhost:8000";
const LOCAL_WEBPAGE_BASE = "http://localhost:5173";
const LOCAL_DASHBOARD_BASE = "http://localhost:5174/dashboard";
const LOCAL_ASSET_BASE = "http://localhost:8000/images";

function isLocalDevPort(port) {
  return ["5173", "5174"].includes(port);
}

function trimTrailingSlash(value) {
  return String(value || "").replace(/\/$/, "");
}

function joinUrl(base, path = "/") {
  const cleanBase = trimTrailingSlash(base);
  const cleanPath = String(path || "/").startsWith("/") ? String(path || "/") : `/${path}`;
  return cleanBase ? `${cleanBase}${cleanPath}` : cleanPath;
}

export const API_BASE = trimTrailingSlash(
  import.meta.env.VITE_API_BASE
  || (isLocalDevPort(location.port) ? LOCAL_API_BASE : "")
);

export const WEBPAGE_BASE = trimTrailingSlash(
  import.meta.env.VITE_WEBPAGE_BASE
  || (location.port === "5174" ? LOCAL_WEBPAGE_BASE : "")
);

export const DASHBOARD_BASE = trimTrailingSlash(
  import.meta.env.VITE_DASHBOARD_BASE
  || (location.port === "5173" ? LOCAL_DASHBOARD_BASE : "/dashboard")
);

export const ASSET_BASE = trimTrailingSlash(
  import.meta.env.VITE_ASSET_BASE
  || (isLocalDevPort(location.port) ? LOCAL_ASSET_BASE : "/images")
);

export function apiUrl(path) {
  return joinUrl(API_BASE, path);
}

export function assetUrl(path = "") {
  const cleanPath = String(path || "")
    .replace(/^\/+/, "")
    .replace(/^images\//, "");
  return joinUrl(ASSET_BASE, cleanPath || "/");
}

export function rewriteAssetUrls(html = "") {
  const prefix = `${assetUrl("").replace(/\/$/, "")}/`;
  return String(html)
    .replaceAll('src="/images/', `src="${prefix}`)
    .replaceAll("src='/images/", `src='${prefix}`);
}

export function webpageUrl(path = "/") {
  return joinUrl(WEBPAGE_BASE, path);
}

export function dashboardUrl(path = "/dashboard/profile/") {
  const normalized = String(path || "/dashboard/profile/");
  const dashboardPath = normalized.startsWith("/dashboard")
    ? normalized.replace(/^\/dashboard/, "") || "/"
    : normalized;
  return joinUrl(DASHBOARD_BASE, dashboardPath);
}

export function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    credentials: "include",
    ...options,
    headers: {
      ...(options.headers || {})
    }
  });
}
