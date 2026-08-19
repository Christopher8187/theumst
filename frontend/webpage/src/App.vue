<script setup>
import { computed, onMounted, watchEffect, ref } from "vue";
import { apiFetch, dashboardUrl } from "../../urls.js";
import AboutPage from "./pages/AboutPage.vue";
import HomePage from "./pages/HomePage.vue";
import ForgotPasswordPage from "./pages/ForgotPasswordPage.vue";
import LoginPage from "./pages/LoginPage.vue";
import NewsPage from "./pages/NewsPage.vue";
import PrivacyPage from "./pages/PrivacyPage.vue";
import ResetPasswordPage from "./pages/ResetPasswordPage.vue";
import SignupPage from "./pages/SignupPage.vue";
import VerifyEmailPage from "./pages/VerifyEmailPage.vue";
import SimplePage from "./pages/SimplePage.vue";
import SiteFooter from "./components/SiteFooter.vue";
import { useWebpageRouter } from "./composables/useWebpageRouter";
import { pages } from "./router/pageMeta";
import { useWebI18n } from "./utils/language";

const { pageName, navigate: routeTo, syncWithBrowser } = useWebpageRouter();
const { tr, setLang } = useWebI18n();
const session = ref({ user: null });
const loginError = ref(new URLSearchParams(location.search).get("error") === "bad-login");
const passwordResetSuccess = ref(new URLSearchParams(location.search).get("reset") === "success");
const emailVerifiedSuccess = ref(
  new URLSearchParams(location.search).get("verified") === "success"
  || new URLSearchParams(location.search).get("email-changed") === "success"
);
const loginMessage = ref("");
const requestedDestination = new URLSearchParams(location.search).get("next") || "";

const pageComponent = computed(() => ({
  home: HomePage,
  about: AboutPage,
  news: NewsPage,
  privacy: PrivacyPage,
  forgotPassword: ForgotPasswordPage,
  login: LoginPage,
  resetPassword: ResetPasswordPage,
  signup: SignupPage,
  verifyEmail: VerifyEmailPage
}[pageName.value] || SimplePage));

const titleKey = computed(() => pages[pageName.value]?.titleKey || "home.title");

function navigate(path) {
  loginError.value = false;
  passwordResetSuccess.value = false;
  emailVerifiedSuccess.value = false;
  loginMessage.value = "";
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

  const data = await res.json().catch(() => ({}));
  if (res.ok) {
    if (data.requires_email_verification) {
      location.href = data.redirect || "/verify-email?sent=1";
      return;
    }
    const safeDestination = requestedDestination.startsWith("/dashboard/")
      ? requestedDestination
      : "/dashboard/profile/";
    location.href = dashboardUrl(safeDestination);
    return;
  }

  if (action === "/auth/login") {
    loginError.value = data.code !== "email_unverified";
    loginMessage.value = data.code === "email_unverified" ? data.detail : "";
    return;
  }

  if (data.code === "email_delivery_failed") {
    location.href = "/verify-email?delivery=failed";
    return;
  }
  alert(data.detail || "Could not sign up.");
}

watchEffect(() => {
  document.title = pageName.value === "home"
    ? "The Ultimate Mega Study Tool"
    : `${tr(titleKey.value)} | The Ultimate Mega Study Tool`;
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
    :password-reset-success="passwordResetSuccess"
    :email-verified-success="emailVerifiedSuccess"
    :login-message="loginMessage"
    @navigate="navigate"
    @set-language="setLang"
    @login="submitAuth($event, '/auth/login')"
    @signup="submitAuth($event, '/auth/signup')"
  />
  <SiteFooter :tr="tr" @navigate="navigate" />
</template>
