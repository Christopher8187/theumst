import { ref } from "vue";
import { pageNameFromPath, pages } from "../router/pageMeta";

function cleanPath(pathname) {
  return pathname.replace(/\/+$/, "") || "/";
}

export function useWebpageRouter() {
  const pageName = ref(pageNameFromPath(location.pathname));

  function isKnownPage(pathname) {
    const path = cleanPath(pathname);
    return Object.values(pages).some(page => cleanPath(page.path) === path);
  }

  function navigate(pathname) {
    const next = pageNameFromPath(pathname);
    pageName.value = next;
    history.pushState(null, "", pages[next]?.path || "/");
  }

  function syncWithBrowser() {
    pageName.value = pageNameFromPath(location.pathname);
  }

  return { pageName, isKnownPage, navigate, syncWithBrowser };
}
