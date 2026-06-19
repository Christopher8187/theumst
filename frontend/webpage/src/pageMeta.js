export const pages = {
  "about": {"path": "/about", "titleKey": "about.title"},
  "get": {"path": "/get", "titleKey": "get.title"},
  "home": {"path": "/", "titleKey": "home.title"},
  "login": {"path": "/login", "titleKey": "login.title"},
  "news": {"path": "/news", "titleKey": "news.title"},
  "signup": {"path": "/signup", "titleKey": "signup.title"},
  "wiki": {"path": "/wiki", "titleKey": "wiki.title"}
};

export function normalizePath(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/index.html") return "/";
  return path.replace(/\.html$/, "");
}

export function pageNameFromPath(pathname) {
  const path = normalizePath(pathname);
  return Object.entries(pages).find(([, page]) => page.path === path)?.[0] || "home";
}
