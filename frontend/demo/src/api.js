const API_BASE = String(
  import.meta.env.VITE_API_BASE || (location.port === "5175" ? "http://localhost:8000" : "")
).replace(/\/$/, "");

export async function demoFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  });
  if (response.status === 401) {
    location.href = "/login";
    throw new Error("Authentication required");
  }
  const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "The demo could not complete that action.");
  return data;
}
