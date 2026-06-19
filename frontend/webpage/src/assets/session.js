export async function refreshSessionCard() {
  const card = document.querySelector("[data-home-user]");
  const login = document.querySelector("[data-nav-login]");

  if (card) card.hidden = true;

  let res;
  try {
    res = await fetch("/api/me", { credentials: "include" });
  } catch {
    return;
  }

  if (!res.ok) return;

  const { user } = await res.json();
  if (login) login.remove();
  if (!card) return;

  card.hidden = false;
  card.querySelector("[data-user-alias]").textContent = user.alias || user.username;
  card.querySelector("[data-user-username]").textContent = user.username;
  card.querySelector("[data-user-description]").textContent = user.description || "No description yet.";
}
