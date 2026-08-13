<script setup>
import { computed, onMounted, ref } from "vue";
import { apiFetch, apiUrl, assetUrl, webpageUrl } from "../../urls.js";
import Sidebar from "./components/Sidebar.vue";
import LanguageModal from "./components/LanguageModal.vue";
import AdminPage from "./pages/AdminPage.vue";
import ApiKeysPage from "./pages/ApiKeysPage.vue";
import BooksPage from "./pages/BooksPage.vue";
import MediaPage from "./pages/MediaPage.vue";
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

const managerUser = ref("");
const managerMessage = ref("");
const managerError = ref(false);

const books = ref([]);
const editingBookId = ref(null);
const bookMessage = ref("");
const bookError = ref(false);
const blankBook = () => ({
  title: "", publisher: "", isbn: "", publish_date: "", version: "", source_key: "", language_id: 1
});
const bookDraft = ref(blankBook());

const posts = ref([]);
const editingPostId = ref(null);
const mediaMessage = ref("");
const mediaError = ref(false);
const blankPost = () => ({ title: "", excerpt: "", body: "", image_url: "/images/graph.jpg", status: "published" });
const postDraft = ref(blankPost());

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
  if (next === "books") loadBooks();
  if (next === "media") loadMedia();
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
  if (route.value === "books") loadBooks();
  if (route.value === "media") loadMedia();
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

async function makeManager() {
  managerMessage.value = "";
  managerError.value = false;
  const res = requireLogin(await apiFetch("/api/admin/make-manager", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: managerUser.value.trim() })
  }));
  const data = await res.json();
  managerError.value = !res.ok;
  managerMessage.value = res.ok ? `${data.user.username} ${t.value.managerGranted}` : data.detail;
  if (res.ok) managerUser.value = "";
}

function setContentMessage(target, errorTarget, value, isError = false) {
  target.value = value;
  errorTarget.value = isError;
}

async function loadBooks() {
  const res = requireLogin(await apiFetch("/api/content/books"));
  const data = await res.json();
  if (!res.ok) return setContentMessage(bookMessage, bookError, data.detail, true);
  books.value = data.books;
}

function resetBook() {
  editingBookId.value = null;
  bookDraft.value = blankBook();
  bookMessage.value = "";
  bookError.value = false;
}

function editBook(book) {
  editingBookId.value = book.grimoire_id;
  bookDraft.value = {
    title: book.title || "",
    publisher: book.publisher || "",
    isbn: book.isbn || "",
    publish_date: book.publish_date || "",
    version: book.version || "",
    source_key: book.source_key || "",
    language_id: Number(book.language_id || 1)
  };
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function saveBook() {
  const path = editingBookId.value ? `/api/content/books/${editingBookId.value}` : "/api/content/books";
  const res = requireLogin(await apiFetch(path, {
    method: editingBookId.value ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bookDraft.value)
  }));
  const data = await res.json();
  if (!res.ok) return setContentMessage(bookMessage, bookError, data.detail, true);
  resetBook();
  setContentMessage(bookMessage, bookError, t.value.bookSaved);
  await loadBooks();
}

async function deleteBook(book) {
  const warning = `${t.value.deleteBookConfirm} “${book.title}”?\n\n${book.section_count} ${t.value.sections}, ${book.knowledge_count} ${t.value.objects}.`;
  if (!confirm(warning)) return;
  const res = requireLogin(await apiFetch(`/api/content/books/${book.grimoire_id}`, { method: "DELETE" }));
  const data = await res.json();
  if (!res.ok) return setContentMessage(bookMessage, bookError, data.detail, true);
  if (editingBookId.value === book.grimoire_id) resetBook();
  setContentMessage(bookMessage, bookError, t.value.bookDeleted);
  await loadBooks();
}

async function loadMedia() {
  const res = requireLogin(await apiFetch("/api/content/media"));
  const data = await res.json();
  if (!res.ok) return setContentMessage(mediaMessage, mediaError, data.detail, true);
  posts.value = data.posts;
}

function resetPost() {
  editingPostId.value = null;
  postDraft.value = blankPost();
  mediaMessage.value = "";
  mediaError.value = false;
}

function editPost(post) {
  editingPostId.value = post.media_post_id;
  postDraft.value = {
    title: post.title || "",
    excerpt: post.excerpt || "",
    body: post.body || "",
    image_url: post.image_url || "",
    status: post.status || "draft"
  };
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function savePost() {
  const path = editingPostId.value ? `/api/content/media/${editingPostId.value}` : "/api/content/media";
  const res = requireLogin(await apiFetch(path, {
    method: editingPostId.value ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(postDraft.value)
  }));
  const data = await res.json();
  if (!res.ok) return setContentMessage(mediaMessage, mediaError, data.detail, true);
  resetPost();
  setContentMessage(mediaMessage, mediaError, t.value.postSaved);
  await loadMedia();
}

async function deletePost(post) {
  if (!confirm(`${t.value.deletePostConfirm} “${post.title}”?`)) return;
  const res = requireLogin(await apiFetch(`/api/content/media/${post.media_post_id}`, { method: "DELETE" }));
  const data = await res.json();
  if (!res.ok) return setContentMessage(mediaMessage, mediaError, data.detail, true);
  if (editingPostId.value === post.media_post_id) resetPost();
  setContentMessage(mediaMessage, mediaError, t.value.postDeleted);
  await loadMedia();
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
    if (route.value === "books") loadBooks();
    if (route.value === "media") loadMedia();
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

      <BooksPage
        v-else-if="route === 'books' && accessPoints.includes('books')"
        v-model:book-draft="bookDraft"
        :t="t"
        :books="books"
        :editing-book-id="editingBookId"
        :message="bookMessage"
        :error="bookError"
        @save="saveBook"
        @edit="editBook"
        @reset="resetBook"
        @delete="deleteBook"
        @refresh="loadBooks"
      />

      <MediaPage
        v-else-if="route === 'media' && accessPoints.includes('media')"
        v-model:post-draft="postDraft"
        :t="t"
        :posts="posts"
        :editing-post-id="editingPostId"
        :message="mediaMessage"
        :error="mediaError"
        @save="savePost"
        @edit="editPost"
        @reset="resetPost"
        @delete="deletePost"
        @refresh="loadMedia"
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
        v-model:manager-user="managerUser"
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
        :manager-message="managerMessage"
        :manager-error="managerError"
        @make-manager="makeManager"
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
