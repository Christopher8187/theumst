import { apiFetch, dashboardUrl } from "../../../urls.js";

export async function updateSessionUI() {
  const card = document.querySelector("[data-home-user]");
  const login = document.querySelector("[data-nav-login]");
  const dashboardLink = document.querySelector("[data-dashboard-link]") || card?.querySelector('a[href^="/dashboard"]');

  if (dashboardLink) dashboardLink.href = dashboardUrl("/dashboard/profile/");

  try {
    const res = await apiFetch("/api/me");
    if (!res.ok) return;

    const { user } = await res.json();
    if (login) login.remove();
    if (!card) return;

    card.hidden = false;
    card.querySelector("[data-user-alias]").textContent = user.alias || user.username;
    card.querySelector("[data-user-username]").textContent = user.username;
    card.querySelector("[data-user-description]").textContent = user.description || "No description yet.";
  } catch {
    // The backend can be offline while testing static pages through Vite.
  }
}
