<script setup>
import { computed, onMounted, watchEffect, ref } from "vue";
import { apiFetch, dashboardUrl } from "../../urls.js";
import AboutPage from "./pages/AboutPage.vue";
import HomePage from "./pages/HomePage.vue";
import LoginPage from "./pages/LoginPage.vue";
import SignupPage from "./pages/SignupPage.vue";
import SimplePage from "./pages/SimplePage.vue";
import { useWebpageRouter } from "./composables/useWebpageRouter";
import { pages } from "./router/pageMeta";
import { useWebI18n } from "./utils/language";

const { pageName, navigate: routeTo, syncWithBrowser } = useWebpageRouter();
const { tr, setLang } = useWebI18n();
const session = ref({ user: null });
const loginError = ref(new URLSearchParams(location.search).get("error") === "bad-login");

const pageComponent = computed(() => ({
  home: HomePage,
  about: AboutPage,
  login: LoginPage,
  signup: SignupPage
}[pageName.value] || SimplePage));

const titleKey = computed(() => pages[pageName.value]?.titleKey || "home.title");

function navigate(path) {
  loginError.value = false;
  routeTo(path);
}

async function loadSession() {
  try {
    const res = await apiFetch("/api/me");
    session.value.user = res.ok ? (await res.json()).user : null;
  } catch {
    session.value.user = null;
  }
}

async function submitAuth(event, action) {
  const res = await apiFetch(action, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: new FormData(event.target)
  });

  if (res.ok) {
    location.href = dashboardUrl("/dashboard/profile/");
    return;
  }

  if (action === "/auth/login") {
    loginError.value = true;
    return;
  }

  const data = await res.json().catch(() => ({ detail: "Could not sign up." }));
  alert(data.detail || "Could not sign up.");
}

watchEffect(() => {
  document.title = tr(titleKey.value);
});

onMounted(() => {
  loadSession();
  window.addEventListener("popstate", syncWithBrowser);
});
</script>

<template>
  <component
    :is="pageComponent"
    :tr="tr"
    :session="session"
    :title-key="titleKey"
    :login-error="loginError"
    @navigate="navigate"
    @set-language="setLang"
    @login="submitAuth($event, '/auth/login')"
    @signup="submitAuth($event, '/auth/signup')"
  />
</template>
