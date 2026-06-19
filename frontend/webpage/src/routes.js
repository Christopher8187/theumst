import home from "./pages/index.html?raw";
import news from "./pages/news.html?raw";
import about from "./pages/about.html?raw";
import wiki from "./pages/wiki.html?raw";
import get from "./pages/get.html?raw";
import login from "./pages/login.html?raw";
import signup from "./pages/signup.html?raw";

export const routes = {
  "/": { html: home, title: "home.title" },
  "/news": { html: news, title: "news.title" },
  "/about": { html: about, title: "about.title" },
  "/wiki": { html: wiki, title: "wiki.title" },
  "/get": { html: get, title: "get.title" },
  "/login": { html: login, title: "login.title" },
  "/signup": { html: signup, title: "signup.title" }
};

export function normalizePath(pathname) {
  if (!pathname || pathname === "/index.html") return "/";
  const withoutTrailing = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return withoutTrailing.replace(/\.html$/, "") || "/";
}

export function resolveRoute(pathname) {
  const path = normalizePath(pathname);
  return routes[path] ? { path, ...routes[path] } : { path: "/", ...routes["/"] };
}
