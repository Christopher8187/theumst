<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { apiFetch, dashboardUrl } from "@shared/urls";
import { closeLanguageMenus, setLanguage, toggleLanguageMenu } from "./language";
import { pageNameFromPath, pages } from "./pageMeta";
import { updateSessionUI } from "./session";
import aboutHtml from "./pages/about.html?raw";
import getHtml from "./pages/get.html?raw";
import homeHtml from "./pages/home.html?raw";
import loginHtml from "./pages/login.html?raw";
import newsHtml from "./pages/news.html?raw";
import signupHtml from "./pages/signup.html?raw";
import wikiHtml from "./pages/wiki.html?raw";

const pageHtmlByName = {
  "about": aboutHtml,
  "get": getHtml,
  "home": homeHtml,
  "login": loginHtml,
  "news": newsHtml,
  "signup": signupHtml,
  "wiki": wikiHtml
};

const pageName = ref(pageNameFromPath(location.pathname));
const pageHtml = computed(() => pageHtmlByName[pageName.value] || pageHtmlByName.home);
const page = computed(() => pages[pageName.value] || pages.home);

function syncPage() {
  document.body.dataset.title = page.value.titleKey;
  setLanguage();
  updateSessionUI();
  const errorEl = document.querySelector("[data-login-error]");
  if (errorEl) errorEl.hidden = new URLSearchParams(location.search).get("error") !== "bad-login";
}

function normalizeRoutePath(pathname) {
  return pathname.replace(/\/+$/, "") || "/";
}

function isKnownPage(pathname) {
  const path = normalizeRoutePath(pathname);
  return Object.values(pages).some(page => normalizeRoutePath(page.path) === path);
}

function navigate(path) {
  const targetName = pageNameFromPath(path);
  pageName.value = targetName;
  history.pushState(null, "", pages[targetName]?.path || "/");
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
    const errorEl = document.querySelector("[data-login-error]");
    if (errorEl) errorEl.hidden = false;
  } else {
    const data = await res.json().catch(() => ({ detail: "Could not sign up." }));
    alert(data.detail || "Could not sign up.");
  }
}

watch(pageName, async () => {
  await nextTick();
  syncPage();
});

onMounted(() => {
  syncPage();
  window.addEventListener("popstate", () => {
    pageName.value = pageNameFromPath(location.pathname);
  });
  document.addEventListener("click", event => {
    if (event.target.closest(".language-menu")) return;
    closeLanguageMenus();
  });
});
</script>

<template>
  <div v-html="pageHtml" @click="handleClick" @submit="handleSubmit"></div>
</template>
