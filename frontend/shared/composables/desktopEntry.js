// Old bookmarks and email links choose an initial window. The address bar then
// belongs to the desktop, not its windows; tokens remain only in component state.
export function consumeDesktopEntry() {
  const entry = new URL(location.href);
  if (entry.pathname !== "/" || entry.search || entry.hash) {
    history.replaceState(null, "", "/");
  }
  return entry;
}
