// Old bookmarks and email links choose an initial window. The address bar then
// belongs to the desktop, not its windows; tokens remain only in component state.
export function consumeDesktopEntry() {
  const entry = new URL(location.href);
  if (entry.pathname !== "/" || entry.search || entry.hash) {
    history.replaceState(null, "", "/");
  }
  return entry;
}

// Only the Demo leaves the desktop after authentication. Do not accept arbitrary
// destinations from a login query string.
export function demoReturnUrl(destination, currentUrl) {
  if (destination !== "/demo" && destination !== "/demo/") return null;
  const url = new URL(currentUrl);
  if (["5173", "5174"].includes(url.port)) {
    url.port = "5175";
    return `${url.origin}/demo/`;
  }
  return "/demo/";
}
