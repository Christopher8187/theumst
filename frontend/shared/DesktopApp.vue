<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { apiFetch } from "../urls.js";
import { pages, pageNameFromPath } from "../webpage/src/router/pageMeta.js";
import { useWebI18n } from "../webpage/src/utils/language.js";
import { routeFromPath } from "../dashboard/src/router/index.js";
import LoginPage from "../webpage/src/pages/LoginPage.vue";
import SignupPage from "../webpage/src/pages/SignupPage.vue";
import ForgotPasswordPage from "../webpage/src/pages/ForgotPasswordPage.vue";
import ResetPasswordPage from "../webpage/src/pages/ResetPasswordPage.vue";
import VerifyEmailPage from "../webpage/src/pages/VerifyEmailPage.vue";
import AboutPage from "../webpage/src/pages/AboutPage.vue";
import SimplePage from "../webpage/src/pages/SimplePage.vue";
import PrivacyPage from "../webpage/src/pages/PrivacyPage.vue";
import DesktopWindow from "./components/DesktopWindow.vue";
import DesktopChrome from "./components/DesktopChrome.vue";
import SceneBackground from "./components/SceneBackground.vue";
import SettingsPanel from "./components/SettingsPanel.vue";
import ProfileContent from "./components/ProfileContent.vue";
import MemberCard from "./components/MemberCard.vue";
import HomeContent from "./components/HomeContent.vue";
import NewsContent from "./components/NewsContent.vue";
import { useDesktopWindows } from "./composables/useDesktopWindows.js";
import { readPreferences, savePreferences } from "./composables/preferences.js";
import { desktopText, roleName } from "./desktopText.js";
import "./desktop.css";
const DashboardTools = defineAsyncComponent(
  () => import("../dashboard/src/components/DashboardTools.vue"),
);
const pageComponents: any = {
  about: AboutPage,
  wiki: SimplePage,
  get: SimplePage,
  login: LoginPage,
  signup: SignupPage,
  forgotPassword: ForgotPasswordPage,
  resetPassword: ResetPasswordPage,
  verifyEmail: VerifyEmailPage,
  privacy: PrivacyPage,
};
const { lang, tr, setLang } = useWebI18n();
const labels = computed(() => desktopText(lang.value));
const { windows, active, open, close, toggle } = useDesktopWindows();
const user = ref<any>(null),
  loadingSession = ref(true),
  sessionError = ref("");
const session = computed(() => ({ user: user.value }));
const scene = ref<any>(),
  sceneState = ref<any>({
    heading: 23,
    auto: !matchMedia("(prefers-reduced-motion: reduce)").matches,
  });
const palette = ref(readPreferences().palette === "blue" ? "blue" : "paper");
watch(
  palette,
  (value) => {
    document.documentElement.dataset.palette = value;
    savePreferences({ palette: value });
  },
  { immediate: true },
);
const dashboardRoute = ref("demo"),
  newsSlug = ref(""),
  profileTab = ref("details");
const query = new URLSearchParams(location.search);
const loginError = ref(query.get("error") === "bad-login"),
  loginMessage = ref(""),
  authBusy = ref(false);
const resetSuccess = query.get("reset") === "success",
  verifiedSuccess =
    query.get("verified") === "success" ||
    query.get("email-changed") === "success";
const requestedDestination = ref(query.get("next") || "");
const initialPath = location.pathname;
function updateUrl(path: string) {
  if (location.pathname !== path) history.pushState(null, "", path);
}
function focus(id: string) {
  open(id);
}
function show(id: string, changeUrl = true) {
  if (id === "profile" && !user.value) {
    id = "login";
  }
  if (id === "profile") profileTab.value = "details";
  open(id);
  if (changeUrl) {
    const path = id === "profile" ? "/dashboard/profile/" : pages[id]?.path;
    if (path) updateUrl(path);
  }
}
function closePage(id: string) {
  close(id);
  if (id === "profile") profileTab.value = "details";
  requestAnimationFrame(() => {
    const selector =
      id === "profile"
        ? ".account-button"
        : id === "card"
          ? ".profile-actions button"
          : id === "dashboard"
            ? ".profile-actions .primary"
            : `.dock-item[data-page="${id}"]`;
    const button = document.querySelector<HTMLButtonElement>(selector);
    const target = button?.getClientRects().length
      ? button
      : document.querySelector<HTMLElement>(
          `.window[data-page="${active.value}"]`,
        );
    target?.focus({ preventScroll: true });
  });
}
function dockToggle(id: string) {
  if (windows.value.some((w) => w.id === id && w.open)) closePage(id);
  else show(id);
}
function navigate(path: string) {
  if (path.startsWith("/dashboard")) {
    if (path.includes("/profile")) show("profile");
    else openDashboard(routeFromPath(path));
    return;
  }
  const url = new URL(path, location.origin);
  if (url.searchParams.has("next"))
    requestedDestination.value = url.searchParams.get("next") || "";
  show(pageNameFromPath(url.pathname));
}
function openDashboard(route = dashboardRoute.value) {
  if (!user.value) {
    requestedDestination.value = "/dashboard/" + route + "/";
    show("login");
    return;
  }
  dashboardRoute.value = route;
  open("profile");
  open("dashboard");
  updateUrl("/dashboard/" + route + "/");
}
function subscriptions() {
  if (!user.value) {
    show("login");
    return;
  }
  open("profile");
  profileTab.value = "subscriptions";
  updateUrl("/dashboard/profile/");
}
function article(slug: string) {
  newsSlug.value = slug;
  open("news");
  updateUrl("/news/" + encodeURIComponent(slug));
}
function syncPath() {
  const path = location.pathname;
  if (path.startsWith("/dashboard/")) {
    if (path.includes("/profile")) show("profile", false);
    else openDashboard(routeFromPath(path));
  } else if (path.startsWith("/news/")) {
    newsSlug.value = decodeURIComponent(path.slice(6));
    open("news");
  } else show(pageNameFromPath(path), false);
}
async function loadSession() {
  loadingSession.value = true;
  sessionError.value = "";
  try {
    const response = await apiFetch("/api/me");
    if (response.ok) user.value = (await response.json()).user;
    else if (response.status === 401) user.value = null;
    else throw Error(labels.value.loadError);
  } catch (e: any) {
    sessionError.value = e.message;
  } finally {
    loadingSession.value = false;
  }
}
async function submitAuth(event: Event, action: string) {
  if (authBusy.value) return;
  authBusy.value = true;
  loginError.value = false;
  loginMessage.value = "";
  try {
    const response = await apiFetch(action, {
      method: "POST",
      headers: { Accept: "application/json" },
      body: new FormData(event.target as HTMLFormElement),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (data.code === "email_delivery_failed") {
        location.href = "/verify-email?delivery=failed";
        return;
      }
      loginError.value =
        action === "/auth/login" && data.code !== "email_unverified";
      loginMessage.value = data.detail || labels.value.accountError;
      return;
    }
    if (data.requires_email_verification) {
      location.href = data.redirect || "/verify-email?sent=1";
      return;
    }
    await loadSession();
    if (!user.value) throw Error(labels.value.accountError);
    close("login");
    close("signup");
    if (
      requestedDestination.value.startsWith("/dashboard/") &&
      !requestedDestination.value.includes("/profile")
    )
      openDashboard(routeFromPath(requestedDestination.value));
    else show("profile");
  } catch (e: any) {
    loginMessage.value = e.message;
  } finally {
    authBusy.value = false;
  }
}
async function signout() {
  try {
    const res = await apiFetch("/auth/signout", { method: "POST" });
    if (!res.ok) throw Error(labels.value.accountError);
    location.href = "/";
  } catch (e: any) {
    sessionError.value = e.message;
  }
}
function downloadCard() {
  if (!user.value) return;
  const escape = (text: string) =>
    String(text).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&apos;",
        })[c]!,
    );
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="540"><rect width="900" height="540" fill="#183a50"/><g fill="#e8e8d0"><text x="60" y="75" font-family="monospace" font-size="23" letter-spacing="5">THEUMST</text><text x="60" y="270" font-family="Georgia,serif" font-size="75">${escape(roleName(user.value.authority_type))}</text><text x="60" y="340" font-family="monospace" font-size="26">${escape(user.value.alias || user.value.username)}</text><text x="60" y="485" font-family="monospace" font-size="17" letter-spacing="3">AT HOME BETWEEN WORLDS</text></g><circle cx="795" cy="250" r="170" fill="none" stroke="#b4c8bb" opacity=".3"/></svg>`;
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "theumst-member-card.svg";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
watch(
  [active, lang],
  ([id]) => {
    document.title =
      id && id !== "home"
        ? `${labels.value[id] || "Theumst"} | Theumst`
        : "Theumst";
  },
  { immediate: true },
);
onMounted(async () => {
  if (!initialPath.startsWith("/dashboard/")) syncPath();
  await loadSession();
  if (initialPath.startsWith("/dashboard/")) {
    if (user.value) syncPath();
    else {
      requestedDestination.value = initialPath;
      show("login");
    }
  }
  addEventListener("popstate", syncPath);
});
onBeforeUnmount(() => removeEventListener("popstate", syncPath));
</script>
<template>
  <SceneBackground
    ref="scene"
    :label="labels.environment"
    @state="sceneState = $event"
  />
  <DesktopChrome
    :signed-in="!!user"
    :labels="labels"
    :open-pages="windows.filter((w) => w.open).map((w) => w.id)"
    @open="show"
    @toggle="dockToggle"
  />
  <main id="windows" :aria-label="labels.pages">
    <DesktopWindow
      v-for="(w, i) in windows"
      :key="w.id"
      :id="w.id"
      :title="labels[w.id] || 'Theumst'"
      :open="w.open"
      :active="active === w.id"
      :order="w.order"
      :offset="i % 5"
      :labels="labels"
      @focus="focus(w.id)"
      @close="closePage(w.id)"
    >
      <HomeContent
        v-if="w.id === 'home'"
        :language="lang"
        :labels="labels"
        @demo="show('demo')"
        @about="show('about')"
      />
      <SettingsPanel
        v-else-if="w.id === 'settings'"
        :labels="labels"
        :language="lang"
        :palette="palette"
        :scene="sceneState"
        @palette="palette = $event"
        @language="setLang"
        @setting="(key, value) => scene?.setting(key, value)"
        @reset="scene?.reset()"
        @privacy="show('privacy')"
      />
      <ProfileContent
        v-else-if="w.id === 'profile' && user"
        :user="user"
        :labels="labels"
        :language="lang"
        :open="w.open"
        :requested-tab="profileTab"
        @updated="user = $event"
        @dashboard="openDashboard()"
        @card="open('card')"
        @news="show('news')"
        @signout="signout"
      />
      <div v-else-if="w.id === 'card' && user" class="member-card-content">
        <MemberCard :user="user" large />
        <div class="button-row">
          <button @click="downloadCard">{{ labels.downloadCard }} ↓</button
          ><button class="primary" @click="closePage('card')">
            {{ labels.finish }}
          </button>
        </div>
      </div>
      <DashboardTools
        v-else-if="w.id === 'dashboard' && user"
        :initial-route="dashboardRoute"
        :language="lang"
        @route-change="
          dashboardRoute = $event;
          updateUrl('/dashboard/' + $event + '/');
        "
        @back-profile="
          closePage('dashboard');
          show('profile');
        "
      />
      <NewsContent
        v-else-if="w.id === 'news'"
        :labels="labels"
        :language="lang"
        :slug="newsSlug"
        :open="w.open"
        @subscriptions="subscriptions"
        @article="article"
      />
      <div v-else-if="w.id === 'demo'" class="page-content">
        <div class="kicker">THEUMST</div>
        <h2>
          {{
            lang === "zh"
              ? "下一页正等着你。"
              : lang === "ja"
                ? "次のページが待っています。"
                : "Your next page is waiting."
          }}
        </h2>
        <p class="lede">
          {{
            lang === "zh"
              ? "进入一本魔典，探索它的想法。"
              : lang === "ja"
                ? "グリモアを開き、考えを探求しましょう。"
                : "Enter a grimoire and explore its ideas."
          }}
        </p>
        <button class="primary" @click="openDashboard('demo')">
          {{ labels.demo }} ↗
        </button>
      </div>
      <component
        v-else-if="pageComponents[w.id]"
        :is="pageComponents[w.id]"
        :tr="tr"
        :session="session"
        :title-key="pages[w.id]?.titleKey"
        :login-error="loginError"
        :password-reset-success="resetSuccess"
        :email-verified-success="verifiedSuccess"
        :login-message="loginMessage"
        :auth-busy="authBusy"
        :news-label="labels.subscribe"
        :optional-label="labels.optional"
        @navigate="navigate"
        @set-language="setLang"
        @login="submitAuth($event, '/auth/login')"
        @signup="submitAuth($event, '/auth/signup')"
      />
    </DesktopWindow>
  </main>
  <nav class="scene-controls" :aria-label="labels.sceneNavigation">
    <span id="heading" :aria-label="labels.direction"
      >{{ Math.round(sceneState.heading) % 360 }}°</span
    ><button :aria-label="labels.library" @click="scene?.look('library')">
      ⌂</button
    ><button :aria-label="labels.left" @click="scene?.look(-25)">←</button
    ><button
      :aria-label="sceneState.auto ? labels.pause : labels.resume"
      @click="scene?.toggle()"
    >
      {{ sceneState.auto ? "Ⅱ" : "▷" }}</button
    ><button :aria-label="labels.right" @click="scene?.look(25)">→</button
    ><button :aria-label="labels.cave" @click="scene?.look('cave')">◇</button>
  </nav>
  <div v-if="sessionError" class="notice visible" role="alert">
    {{ sessionError }} <button @click="loadSession">{{ labels.retry }}</button>
  </div>
</template>
