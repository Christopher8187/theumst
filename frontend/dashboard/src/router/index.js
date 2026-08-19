export const dashboardRoutes = {
  profile: "/dashboard/profile/",
  "api-keys": "/dashboard/api-keys/",
  demo: "/dashboard/demo/",
  books: "/dashboard/books/",
  users: "/dashboard/users/",
  media: "/dashboard/media/",
  admin: "/dashboard/admin/",
  superadmin: "/dashboard/superadmin/"
};

export function routeFromPath(pathname = location.pathname) {
  if (pathname.includes("superadmin")) return "superadmin";
  if (pathname.includes("admin")) return "admin";
  if (pathname.includes("demo")) return "demo";
  if (pathname.includes("users")) return "users";
  if (pathname.includes("books")) return "books";
  if (pathname.includes("media")) return "media";
  if (pathname.includes("api-keys")) return "api-keys";
  return "profile";
}

export function canUseRoute(route, accessPoints = []) {
  if (route === "demo") return accessPoints.includes("profile");
  if (route === "users") return accessPoints.includes("admin");
  return accessPoints.includes(route);
}
