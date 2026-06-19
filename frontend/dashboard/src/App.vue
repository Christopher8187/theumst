<script setup>
import { computed, onMounted, ref } from "vue";
import { useI18n } from "./i18n";
import { apiFetch, apiUrl, webpageUrl } from "../../urls.js";

const { lang, t, setLang } = useI18n();

const routes = {
  profile: "/dashboard/profile/",
  "api-keys": "/dashboard/api-keys/",
  admin: "/dashboard/admin/",
  superadmin: "/dashboard/superadmin/"
};

const route = ref(getRoute());
const message = ref("");
const output = ref("");
const outputError = ref(false);
const keys = ref([]);
const profile = ref({ username: "", email: "", alias: "", description: "", authority_type: "" });
const adminSql = ref("");
const adminResult = ref("");
const adminError = ref(false);
const storagePath = ref("");
const storageMode = ref("");
const storageItems = ref([]);
const storageText = ref("");
const storageFile = ref("");
const storageName = ref("");
const folderName = ref("");
const storageMessage = ref("");
const storageError = ref(false);
const uploadInput = ref(null);
const superUser = ref("");
const superMessage = ref("");
const superError = ref(false);
const showLanguage = ref(false);
const logoSrc = "/images/logo.png";
const translateSrc = "/images/translate.svg";

const isProfile = computed(() => route.value === "profile");
const isApiKeys = computed(() => route.value === "api-keys");
const isAdmin = computed(() => ["admin", "superadmin"].includes(profile.value.authority_type));
const isSuperadmin = computed(() => profile.value.authority_type === "superadmin");
const parentPath = computed(() => storagePath.value.split("/").slice(0, -1).join("/"));

function getRoute() {
  if (location.pathname.includes("superadmin")) return "superadmin";
  if (location.pathname.includes("admin")) return "admin";
  if (location.pathname.includes("api-keys")) return "api-keys";
  return "profile";
}

function go(next) {
  route.value = next;
  history.pushState(null, "", routes[next]);
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

function enforceRolePage() {
  if ((route.value === "admin" && !isAdmin.value) || (route.value === "superadmin" && !isSuperadmin.value)) {
    go("profile");
  }
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
  const data = await res.json();
  profile.value = data.user;
  enforceRolePage();
  if (route.value === "admin" && isAdmin.value) loadStorage();
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

  if (!res.ok) {
    output.value = (await res.json()).detail;
    outputError.value = true;
    return;
  }

  output.value = `${t.value.newKey} ${(await res.json()).key}`;
  outputError.value = false;
  event.target.reset();
  loadKeys();
}

async function revokeKey(id) {
  await apiFetch(`/api/api-keys/${id}`, { method: "DELETE" });
  loadKeys();
}

async function runSql() {
  adminResult.value = "";
  adminError.value = false;

  const res = requireLogin(await apiFetch("/api/admin/sql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql: adminSql.value })
  }));

  const data = await res.json();
  adminError.value = !res.ok;
  adminResult.value = res.ok ? JSON.stringify(data, null, 2) : data.detail;
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

async function signOut() {
  await apiFetch("/auth/signout", { method: "POST" });
  location.href = webpageUrl("/");
}

onMounted(() => {
  loadProfile();
  loadKeys();
  window.addEventListener("popstate", () => {
    route.value = getRoute();
    enforceRolePage();
    if (route.value === "admin" && isAdmin.value) loadStorage();
  });
});
</script>

<template>
  <div class="dashboard-shell">
    <aside class="sidebar">
      <a :href="webpageUrl('/')"><img class="dash-logo" :src="logoSrc" alt="UMST"></a>

      <a class="side-link" :href="webpageUrl('/')">{{ t.home }}</a>
      <button class="side-link" :class="{ active: isProfile }" @click="go('profile')">{{ t.profile }}</button>
      <button class="side-link" :class="{ active: isApiKeys }" @click="go('api-keys')">{{ t.apiKeys }}</button>
      <button v-if="isAdmin" class="side-link" :class="{ active: route === 'admin' }" @click="go('admin')">{{ t.admin }}</button>
      <button v-if="isSuperadmin" class="side-link" :class="{ active: route === 'superadmin' }" @click="go('superadmin')">{{ t.superadmin }}</button>

      <button class="language-trigger" @click="showLanguage = true">
        <img :src="translateSrc" alt="">
        <span>{{ t.language }}</span>
      </button>

      <button class="side-link signout" @click="signOut">{{ t.signOut }}</button>
    </aside>

    <main class="dashboard-main">
      <section v-if="isProfile" class="dashboard-card">
        <p class="eyebrow">{{ t.identity }}</p>
        <h1>{{ t.profileTitle }}</h1>
        <p class="muted">{{ t.profileText }}</p>

        <div class="readonly-field">
          <span>{{ t.authorityType }}</span>
          <strong>{{ profile.authority_type }}</strong>
        </div>

        <form class="dashboard-form" @submit.prevent="saveProfile">
          <label>{{ t.username }}<input v-model="profile.username" required></label>
          <label>{{ t.email }}<input v-model="profile.email" type="email" required></label>
          <label>{{ t.alias }}<input v-model="profile.alias"></label>
          <label>{{ t.description }}<textarea v-model="profile.description" rows="5"></textarea></label>
          <button type="submit">{{ t.saveProfile }}</button>
          <p class="message">{{ message }}</p>
        </form>
      </section>

      <section v-else-if="isApiKeys" class="dashboard-card">
        <p class="eyebrow">{{ t.developer }}</p>
        <h1>{{ t.apiTitle }}</h1>
        <p class="muted">{{ t.apiText }}</p>

        <form class="dashboard-form small-form" @submit.prevent="createKey" novalidate>
          <label>{{ t.keyName }}<input name="name" autocomplete="off"></label>
          <button type="submit">{{ t.createKey }}</button>
        </form>

        <p class="message key-output" :class="{ error: outputError }" v-if="output">{{ output }}</p>

        <div class="key-list">
          <article v-for="key in keys" :key="key.api_key_id" class="key-row" :class="{ revoked: key.revoked_at }">
            <div>
              <h3>{{ key.name }}</h3>
              <p>{{ key.key_prefix }}… {{ key.revoked_at ? t.revoked : t.active }}</p>
            </div>
            <button v-if="!key.revoked_at" @click="revokeKey(key.api_key_id)">{{ t.revoke }}</button>
          </article>
        </div>
      </section>

      <section v-else-if="route === 'admin' && isAdmin" class="dashboard-card wide-card">
        <p class="eyebrow">{{ t.admin }}</p>
        <h1>{{ t.adminTitle }}</h1>
        <p class="muted">{{ t.adminText }}</p>

        <form class="dashboard-form" @submit.prevent="runSql">
          <label>{{ t.sqlCode }}<textarea v-model="adminSql" class="sql-box" rows="10"></textarea></label>
          <button type="submit">{{ t.runSql }}</button>
        </form>

        <pre v-if="adminResult" class="result-box" :class="{ error: adminError }">{{ adminResult }}</pre>

        <section class="storage-panel">
          <div class="storage-head">
            <div>
              <p class="eyebrow">{{ t.files }}</p>
              <h2>{{ t.objectStorage }}</h2>
              <p class="muted">{{ t.storageText }} <strong>{{ storageMode }}</strong></p>
            </div>
            <button type="button" @click="loadStorage()">{{ t.refresh }}</button>
          </div>

          <div class="storage-tools">
            <button type="button" :disabled="!storagePath" @click="loadStorage(parentPath)">← {{ t.up }}</button>
            <span class="path-pill">/{{ storagePath }}</span>
          </div>

          <div class="storage-actions">
            <form @submit.prevent="createFolder">
              <input v-model="folderName" :placeholder="t.newFolder" autocomplete="off">
              <button type="submit">{{ t.createFolder }}</button>
            </form>
            <button type="button" @click="newStorageFile">{{ t.newFile }}</button>
            <button type="button" @click="uploadInput.click()">{{ t.upload }}</button>
            <input ref="uploadInput" class="hidden-file" type="file" @change="uploadFile">
          </div>

          <div class="storage-grid">
            <div class="file-list">
              <article v-for="item in storageItems" :key="item.key" class="file-row">
                <button class="file-name" type="button" @click="openStorage(item)">
                  <span>{{ item.type === 'folder' ? '📁' : '📄' }}</span>
                  <strong>{{ item.name }}</strong>
                </button>
                <span>{{ item.type }}</span>
                <span>{{ niceSize(item.size) }}</span>
                <div class="file-buttons">
                  <a v-if="item.type === 'file'" :href="apiUrl(`/api/admin/storage/download?path=${encodeURIComponent(item.key)}`)">{{ t.download }}</a>
                  <button type="button" @click="deleteStorage(item)">{{ t.delete }}</button>
                </div>
              </article>
              <p v-if="!storageItems.length" class="empty-list">{{ t.emptyFolder }}</p>
            </div>

            <form class="storage-editor" @submit.prevent="saveStorage">
              <label>{{ t.filePath }}<input v-model="storageName" autocomplete="off" :placeholder="storagePath ? `${storagePath}/notes.txt` : 'notes.txt'"></label>
              <label>{{ t.fileContent }}<textarea v-model="storageText" rows="14"></textarea></label>
              <button type="submit">{{ t.saveFile }}</button>
              <p v-if="storageMessage" class="message key-output" :class="{ error: storageError }">{{ storageMessage }}</p>
            </form>
          </div>
        </section>
      </section>

      <section v-else-if="route === 'superadmin' && isSuperadmin" class="dashboard-card">
        <p class="eyebrow">{{ t.superadmin }}</p>
        <h1>{{ t.superadminTitle }}</h1>
        <p class="muted">{{ t.superadminText }}</p>

        <form class="dashboard-form small-form" @submit.prevent="makeAdmin" novalidate>
          <label>{{ t.userToPromote }}<input v-model="superUser" autocomplete="off"></label>
          <button type="submit">{{ t.giveAdmin }}</button>
        </form>

        <p v-if="superMessage" class="message key-output" :class="{ error: superError }">{{ superMessage }}</p>
      </section>
    </main>

    <div v-if="showLanguage" class="language-modal-backdrop" @click.self="showLanguage = false">
      <section class="language-modal">
        <button class="modal-close" @click="showLanguage = false">×</button>
        <img class="modal-language-icon" :src="translateSrc" alt="">
        <h2>{{ t.chooseLanguage }}</h2>
        <p>{{ t.chooseLanguageText }}</p>

        <button class="language-option" :class="{ active: lang === 'en' }" @click="chooseLang('en')">English</button>
        <button class="language-option" :class="{ active: lang === 'zh' }" @click="chooseLang('zh')">中文</button>
        <button class="language-option" :class="{ active: lang === 'ja' }" @click="chooseLang('ja')">日本語</button>
      </section>
    </div>
  </div>
</template>
