<script setup>
import { computed, nextTick, onMounted, watch } from "vue";
import { apiFetch, dashboardUrl } from "../../urls.js";
import RawPage from "./components/RawPage.vue";
import { useWebpageRouter } from "./composables/useWebpageRouter";
import { pageHtml } from "./pages";
import { pages } from "./router/pageMeta";
import { closeLanguageMenus, setLanguage, toggleLanguageMenu } from "./utils/language";
import { updateSessionUI } from "./utils/session";

const { pageName, isKnownPage, navigate, syncWithBrowser } = useWebpageRouter();
const page = computed(() => pages[pageName.value] || pages.home);
const html = computed(() => pageHtml[pageName.value] || pageHtml.home);

function syncPage() {
  document.body.dataset.title = page.value.titleKey;
  setLanguage();
  updateSessionUI();

  const error = document.querySelector("[data-login-error]");
  if (error) error.hidden = new URLSearchParams(location.search).get("error") !== "bad-login";
}

function handleClick(event) {
  const languageButton = event.target.closest("[data-language-button]");
  if (languageButton) {
    event.preventDefault();
    toggleLanguageMenu(languageButton);
    return;
  }

  const languageChoice = event.target.closest("[data-language-choice]");
  if (languageChoice) {
    event.preventDefault();
    setLanguage(languageChoice.dataset.languageChoice);
    return;
  }

  const link = event.target.closest("a[href]");
  if (!link) return;

  const url = new URL(link.href, location.href);
  if (url.pathname.startsWith("/dashboard")) {
    event.preventDefault();
    location.href = dashboardUrl(url.pathname);
    return;
  }

  if (url.origin === location.origin && isKnownPage(url.pathname)) {
    event.preventDefault();
    navigate(url.pathname);
  }
}

async function handleSubmit(event) {
  const form = event.target;
  const action = form.getAttribute("action") || "";
  if (!["/auth/login", "/auth/signup"].includes(action)) return;

  event.preventDefault();
  const res = await apiFetch(action, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: new FormData(form)
  });

  if (res.ok) {
    location.href = dashboardUrl("/dashboard/profile/");
    return;
  }

  if (action === "/auth/login") {
    const error = document.querySelector("[data-login-error]");
    if (error) error.hidden = false;
    return;
  }

  const data = await res.json().catch(() => ({ detail: "Could not sign up." }));
  alert(data.detail || "Could not sign up.");
}

watch(pageName, async () => {
  await nextTick();
  syncPage();
});

onMounted(() => {
  syncPage();
  window.addEventListener("popstate", syncWithBrowser);
  document.addEventListener("click", event => {
    if (!event.target.closest(".language-menu")) closeLanguageMenus();
  });
});
</script>

<template>
  <RawPage :html="html" @page-click="handleClick" @page-submit="handleSubmit" />
</template>
