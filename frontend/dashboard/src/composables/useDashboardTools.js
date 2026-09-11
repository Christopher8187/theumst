import { computed, onMounted, ref, toValue, watch } from "vue";
import { apiFetch, webpageUrl } from "../../../urls.js";
import { canUseRoute } from "../router";
import { useMediaPosts } from "./useMediaPosts.js";

// Browser history and window visibility belong to DesktopApp; tool drafts live here.
export function useDashboardTools({ initialRoute, onRouteChange, scrollToEditor, t }) {
  const route = ref(toValue(initialRoute) || "demo");
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

  const {
    posts, editingPostId, mediaMessage, mediaError, mediaSaving, postDraft, announcementQueued, createRetryPending, retryCreate,
    emailPreview, previewLoading, previewError, loadMedia, resetPost, editPost, savePost, deletePost, previewEmail
  } = useMediaPosts({ t, requireLogin, scrollToEditor });

  const demoAccess = ref(null);
  const demoRequests = ref([]);
  const demoLoading = ref(false);
  const demoMessage = ref("");
  const demoError = ref(false);

  const users = ref([]);
  const usersLoading = ref(false);
  const usersMessage = ref("");
  const usersError = ref(false);

  const profileLoaded = ref(false);
  const loadingError = ref("");
  const accessPoints = computed(() => profile.value.access_points || []);
  const parentPath = computed(() => storagePath.value.split("/").slice(0, -1).join("/"));
  const demoUrl = computed(() => ["5173", "5174"].includes(location.port) ? "http://localhost:5175/demo/" : "/demo/");

  async function loadRoute(next) {
    if (next === "api-keys") await loadKeys();
    if (next === "admin") await loadStorage();
    if (next === "books") await loadBooks();
    if (next === "users") await loadUsers();
    if (next === "media") await loadMedia();
    if (next === "demo") await loadDemoAccess();
  }

  async function go(next, notify = true) {
    if (!profileLoaded.value || next === "profile" || !canUseRoute(next, accessPoints.value)) return;
    if (route.value === next) return;
    route.value = next;
    scrollToEditor();
    if (notify) onRouteChange(next);
    loadingError.value = "";
    try {
      await loadRoute(next);
    } catch {
      loadingError.value = t.value.dashboardLoadError;
    }
  }

  function requireLogin(res) {
    if (res.status === 401) location.href = webpageUrl("/login");
    return res;
  }

  function accessibleRoute(next) {
    return next !== "profile" && canUseRoute(next, accessPoints.value) ? next : "demo";
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
    loadingError.value = "";
    try {
      const res = requireLogin(await apiFetch("/api/me"));
      if (!res.ok) {
        loadingError.value = t.value.dashboardLoadError;
        return;
      }
      profile.value = (await res.json()).user;
      profileLoaded.value = true;
      const next = accessibleRoute(toValue(initialRoute));
      route.value = next;
      if (next !== toValue(initialRoute)) onRouteChange(next);
      await loadRoute(next);
    } catch {
      loadingError.value = t.value.dashboardLoadError;
    }
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
    scrollToEditor();
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

  async function setBookDemoVisibility(book, enabled) {
    const prompt = enabled
      ? `${t.value.enableDemoConfirm} “${book.title}”?`
      : `${t.value.disableDemoConfirm} “${book.title}”?`;
    if (!confirm(prompt)) return;
    const res = requireLogin(await apiFetch(`/api/content/books/${book.grimoire_id}/demo-visibility`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled })
    }));
    const data = await res.json();
    if (!res.ok) return setContentMessage(bookMessage, bookError, data.detail, true);
    setContentMessage(
      bookMessage,
      bookError,
      enabled ? t.value.demoBookEnabled : t.value.demoBookDisabled
    );
    await loadBooks();
  }

  async function loadUsers() {
    usersLoading.value = true;
    usersMessage.value = "";
    usersError.value = false;
    const res = requireLogin(await apiFetch("/api/admin/users"));
    const data = await res.json();
    usersLoading.value = false;
    if (!res.ok) {
      usersError.value = true;
      usersMessage.value = data.detail;
      return;
    }
    users.value = data.users;
  }

  async function loadDemoAccess() {
    demoLoading.value = true;
    demoMessage.value = "";
    demoError.value = false;
    const res = requireLogin(await apiFetch("/api/demo/access"));
    const data = await res.json();
    if (!res.ok) {
      demoError.value = true;
      demoMessage.value = data.detail;
      demoLoading.value = false;
      return;
    }
    demoAccess.value = data;
    if (data.can_review) await loadDemoRequests();
    demoLoading.value = false;
  }

  async function loadDemoRequests() {
    const res = requireLogin(await apiFetch("/api/demo/access/requests"));
    const data = await res.json();
    if (!res.ok) {
      demoError.value = true;
      demoMessage.value = data.detail;
      return;
    }
    demoRequests.value = data.requests;
  }

  async function requestDemoAccess(requestMessage) {
    const res = requireLogin(await apiFetch("/api/demo/access/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: requestMessage })
    }));
    const data = await res.json();
    demoError.value = !res.ok;
    demoMessage.value = res.ok ? t.value.demoRequestSent : data.detail;
    if (res.ok) await loadDemoAccess();
  }

  async function reviewDemoAccess(userId, decision) {
    const res = requireLogin(await apiFetch(`/api/demo/access/requests/${userId}/${decision}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "" })
    }));
    const data = await res.json();
    demoError.value = !res.ok;
    demoMessage.value = res.ok
      ? (decision === "approve" ? t.value.demoApproved : t.value.demoRejected)
      : data.detail;
    if (res.ok) await loadDemoRequests();
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

  watch(initialRoute, (next) => {
    if (profileLoaded.value) go(accessibleRoute(next), next !== accessibleRoute(next));
  });

  onMounted(loadProfile);

  return {
      route, output, outputError, keys, profileLoaded, loadingError, accessPoints,
      storagePath, storageMode, storageItems, storageText, storageName, folderName, storageMessage, storageError,
      qdrantQuery, qdrantVector, qdrantFilters, qdrantLimit, qdrantResult, qdrantError,
      superUser, superMessage, superError, superSql, superSqlResult, superSqlError,
      managerUser, managerMessage, managerError, books, editingBookId, bookMessage, bookError, bookDraft,
      posts, editingPostId, mediaMessage, mediaError, mediaSaving, postDraft, announcementQueued, createRetryPending, retryCreate,
      emailPreview, previewLoading, previewError, previewEmail,
      demoAccess, demoRequests, demoLoading, demoMessage, demoError,
      users, usersLoading, usersMessage, usersError, parentPath, demoUrl,
      go, loadProfile, createKey, upgradeKey, revokeKey, niceSize, searchQdrant, loadStorage, openStorage,
      saveStorage, createFolder, uploadFile, deleteStorage, newStorageFile, makeAdmin, makeManager,
      loadBooks, resetBook, editBook, saveBook, deleteBook, setBookDemoVisibility, loadUsers,
      loadMedia, resetPost, editPost, savePost, deletePost, loadDemoRequests, requestDemoAccess, reviewDemoAccess, runSuperSql
  };
}
