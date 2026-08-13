export const dashboardRoutes = {
  profile: "/dashboard/profile/",
  "api-keys": "/dashboard/api-keys/",
  books: "/dashboard/books/",
  media: "/dashboard/media/",
  admin: "/dashboard/admin/",
  superadmin: "/dashboard/superadmin/"
};

export function routeFromPath(pathname = location.pathname) {
  if (pathname.includes("superadmin")) return "superadmin";
  if (pathname.includes("admin")) return "admin";
  if (pathname.includes("books")) return "books";
  if (pathname.includes("media")) return "media";
  if (pathname.includes("api-keys")) return "api-keys";
  return "profile";
}

export function canUseRoute(route, accessPoints = []) {
  return accessPoints.includes(route);
}
