<script setup>
import { computed, onMounted, ref } from "vue";
import { apiFetch, apiUrl, assetUrl, webpageUrl } from "../../urls.js";
import Sidebar from "./components/Sidebar.vue";
import LanguageModal from "./components/LanguageModal.vue";
import AdminPage from "./pages/AdminPage.vue";
import ApiKeysPage from "./pages/ApiKeysPage.vue";
import ProfilePage from "./pages/ProfilePage.vue";
import SuperadminPage from "./pages/SuperadminPage.vue";
import { canUseRoute, dashboardRoutes, routeFromPath } from "./router";
import { useI18n } from "./utils/i18n";

const { lang, t, setLang } = useI18n();

const route = ref(routeFromPath());
const message = ref("");
const output = ref("");
const outputError = ref(false);
const keys = ref([]);
const profile = ref({
  username: "", email: "", alias: "", description: "",
  authority_type: "", access_points: []
});

const storagePath = ref("");
const storageMode = ref("");
const storageItems = ref([]);
const storageText = ref("");
const storageFile = ref("");
const storageName = ref("");
const folderName = ref("");
const storageMessage = ref("");
const storageError = ref(false);

const qdrantQuery = ref("");
const qdrantVector = ref("");
const qdrantFilters = ref("{}");
const qdrantLimit = ref(10);
const qdrantResult = ref("");
const qdrantError = ref(false);

const superUser = ref("");
const superMessage = ref("");
const superError = ref(false);
const superSql = ref("");
const superSqlResult = ref("");
const superSqlError = ref(false);

const showLanguage = ref(false);
const logoSrc = assetUrl("logo.png");
const translateSrc = assetUrl("translate.svg");
const accessPoints = computed(() => profile.value.access_points || []);
const parentPath = computed(() => storagePath.value.split("/").slice(0, -1).join("/"));
const homeUrl = computed(() => webpageUrl("/"));

function go(next) {
  if (!canUseRoute(next, accessPoints.value)) return;
  route.value = next;
  history.pushState(null, "", dashboardRoutes[next]);
  if (next === "admin") loadStorage();
}

function chooseLang(value) {
  setLang(value);
  showLanguage.value = false;
}

function requireLogin(res) {
  if (res.status === 401) location.href = webpageUrl("/login");
  return res;
}

function enforceAccessPage() {
  if (!canUseRoute(route.value, accessPoints.value)) go("profile");
}

function joinPath(folder, name) {
  return [folder, name].filter(Boolean).join("/").replaceAll("//", "/");
}

function showStorage(text, isError = false) {
  storageMessage.value = text;
  storageError.value = isError;
}

function niceSize(size) {
  if (!size) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function loadProfile() {
  const res = requireLogin(await apiFetch("/api/me"));
  if (!res.ok) return;
  profile.value = (await res.json()).user;
  enforceAccessPage();
  if (route.value === "admin") loadStorage();
}

async function saveProfile() {
  const res = requireLogin(await apiFetch("/api/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile.value)
  }));
  message.value = res.ok ? t.value.saved : (await res.json()).detail;
}

async function loadKeys() {
  const res = requireLogin(await apiFetch("/api/api-keys"));
  if (!res.ok) return;
  keys.value = (await res.json()).keys;
}

async function createKey(event) {
  const data = Object.fromEntries(new FormData(event.target));
  if (!data.name.trim()) {
    output.value = t.value.keyNameRequired;
    outputError.value = true;
    return;
  }
  const res = requireLogin(await apiFetch("/api/api-keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  }));
  const response = await res.json();
  if (!res.ok) {
    output.value = response.detail;
    outputError.value = true;
    return;
  }
  output.value = `${t.value.newKey} ${response.key}`;
  outputError.value = false;
  event.target.reset();
  loadKeys();
}

async function upgradeKey(id) {
  if (!confirm(t.value.upgradeMasterConfirm)) return;
  const res = requireLogin(await apiFetch(`/api/api-keys/${id}/upgrade-master`, { method: "POST" }));
  const data = await res.json();
  output.value = res.ok ? t.value.masterUpgraded : data.detail;
  outputError.value = !res.ok;
  loadKeys();
}

async function revokeKey(id) {
  await apiFetch(`/api/api-keys/${id}`, { method: "DELETE" });
  loadKeys();
}

async function searchQdrant() {
  qdrantResult.value = "";
  qdrantError.value = false;
  let vector = null;
  let filters = {};
  try {
    if (qdrantVector.value.trim()) vector = JSON.parse(qdrantVector.value);
    filters = qdrantFilters.value.trim() ? JSON.parse(qdrantFilters.value) : {};
  } catch (error) {
    qdrantError.value = true;
    qdrantResult.value = `${t.value.invalidJson}: ${error.message}`;
    return;
  }
  const res = requireLogin(await apiFetch("/api/admin/qdrant/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query_text: qdrantQuery.value.trim() || null,
      query_vector: vector,
      filters,
      limit: Number(qdrantLimit.value || 10)
    })
  }));
  const data = await res.json();
  qdrantError.value = !res.ok;
  qdrantResult.value = res.ok ? JSON.stringify(data, null, 2) : data.detail;
}

async function loadStorage(path = storagePath.value) {
  const res = requireLogin(await apiFetch(`/api/admin/storage?path=${encodeURIComponent(path)}`));
  const data = await res.json();
  if (!res.ok) return showStorage(data.detail, true);
  storagePath.value = data.path;
  storageMode.value = data.mode;
  storageItems.value = data.items;
  showStorage(t.value.storageLoaded);
}

async function openStorage(item) {
  if (item.type === "folder") return loadStorage(item.key);
  const res = requireLogin(await apiFetch(`/api/admin/storage/read?path=${encodeURIComponent(item.key)}`));
  const data = await res.json();
  if (!res.ok) return showStorage(data.detail, true);
  storageFile.value = data.path;
  storageName.value = data.path;
  storageText.value = data.content;
  showStorage(t.value.storageFileLoaded);
}

async function saveStorage() {
  const name = storageName.value.trim();
  const path = storageFile.value || (name.includes("/") ? name : joinPath(storagePath.value, name));
  if (!path) return showStorage(t.value.storagePathRequired, true);
  const res = requireLogin(await apiFetch("/api/admin/storage/write", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content: storageText.value })
  }));
  const data = await res.json();
  if (!res.ok) return showStorage(data.detail, true);
  storageFile.value = path;
  storageName.value = path;
  showStorage(t.value.storageSaved);
  loadStorage();
}

async function createFolder() {
  if (!folderName.value.trim()) return showStorage(t.value.folderNameRequired, true);
  const res = requireLogin(await apiFetch("/api/admin/storage/folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: storagePath.value, name: folderName.value })
  }));
  const data = await res.json();
  if (!res.ok) return showStorage(data.detail, true);
  folderName.value = "";
  showStorage(t.value.folderCreated);
  loadStorage();
}

async function uploadFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("folder", storagePath.value);
  form.append("file", file);
  const res = requireLogin(await apiFetch("/api/admin/storage/upload", { method: "POST", body: form }));
  const data = await res.json();
  if (!res.ok) return showStorage(data.detail, true);
  event.target.value = "";
  showStorage(t.value.fileUploaded);
  loadStorage();
}

async function deleteStorage(item) {
  if (!confirm(`${t.value.deleteConfirm} ${item.name}?`)) return;
  const res = requireLogin(await apiFetch(`/api/admin/storage?path=${encodeURIComponent(item.key)}`, { method: "DELETE" }));
  const data = await res.json();
  if (!res.ok) return showStorage(data.detail, true);
  if (storageFile.value === item.key) {
    storageFile.value = "";
    storageName.value = "";
    storageText.value = "";
  }
  showStorage(t.value.deleted);
  loadStorage();
}

function newStorageFile() {
  storageFile.value = "";
  storageName.value = "";
  storageText.value = "";
  showStorage(t.value.newFileReady);
}

async function makeAdmin() {
  superMessage.value = "";
  superError.value = false;
  const res = requireLogin(await apiFetch("/api/superadmin/make-admin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: superUser.value })
  }));
  const data = await res.json();
  superError.value = !res.ok;
  superMessage.value = res.ok ? `${data.user.username} ${t.value.adminGranted}` : data.detail;
}

async function runSuperSql() {
  superSqlResult.value = "";
  superSqlError.value = false;
  const res = requireLogin(await apiFetch("/api/superadmin/sql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql: superSql.value })
  }));
  const data = await res.json();
  superSqlError.value = !res.ok;
  superSqlResult.value = res.ok ? JSON.stringify(data, null, 2) : data.detail;
}

async function signOut() {
  await apiFetch("/auth/signout", { method: "POST" });
  location.href = webpageUrl("/");
}

onMounted(() => {
  loadProfile();
  loadKeys();
  window.addEventListener("popstate", () => {
    route.value = routeFromPath();
    enforceAccessPage();
    if (route.value === "admin") loadStorage();
  });
});
</script>

<template>
  <div class="dashboard-shell">
    <Sidebar
      :t="t"
      :route="route"
      :access-points="accessPoints"
      :logo-src="logoSrc"
      :translate-src="translateSrc"
      :home-url="homeUrl"
      @go="go"
      @choose-language="showLanguage = true"
      @sign-out="signOut"
    />

    <main class="dashboard-main">
      <ProfilePage
        v-if="route === 'profile'"
        :t="t"
        :profile="profile"
        :message="message"
        @save="saveProfile"
      />

      <ApiKeysPage
        v-else-if="route === 'api-keys'"
        :t="t"
        :keys="keys"
        :output="output"
        :output-error="outputError"
        @create="createKey"
        @upgrade="upgradeKey"
        @revoke="revokeKey"
      />

      <AdminPage
        v-else-if="route === 'admin' && accessPoints.includes('admin')"
        v-model:qdrant-query="qdrantQuery"
        v-model:qdrant-vector="qdrantVector"
        v-model:qdrant-filters="qdrantFilters"
        v-model:qdrant-limit="qdrantLimit"
        v-model:folder-name="folderName"
        v-model:storage-name="storageName"
        v-model:storage-text="storageText"
        :t="t"
        :api-url="apiUrl"
        :nice-size="niceSize"
        :parent-path="parentPath"
        :storage-path="storagePath"
        :storage-mode="storageMode"
        :storage-items="storageItems"
        :storage-message="storageMessage"
        :storage-error="storageError"
        :qdrant-result="qdrantResult"
        :qdrant-error="qdrantError"
        @search-qdrant="searchQdrant"
        @load-storage="loadStorage"
        @open-storage="openStorage"
        @create-folder="createFolder"
        @new-file="newStorageFile"
        @upload-file="uploadFile"
        @delete-storage="deleteStorage"
        @save-storage="saveStorage"
      />

      <SuperadminPage
        v-else-if="route === 'superadmin' && accessPoints.includes('superadmin')"
        v-model:super-user="superUser"
        v-model:super-sql="superSql"
        :t="t"
        :super-message="superMessage"
        :super-error="superError"
        :sql-result="superSqlResult"
        :sql-error="superSqlError"
        @make-admin="makeAdmin"
        @run-sql="runSuperSql"
      />
    </main>

    <LanguageModal
      v-if="showLanguage"
      :t="t"
      :lang="lang"
      :translate-src="translateSrc"
      @close="showLanguage = false"
      @choose="chooseLang"
    />
  </div>
</template>
