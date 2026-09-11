<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { apiUrl } from "../../../urls.js";
import AdminPage from "../pages/AdminPage.vue";
import ApiKeysPage from "../pages/ApiKeysPage.vue";
import BooksPage from "../pages/BooksPage.vue";
import DemoPage from "../pages/DemoPage.vue";
import MediaPage from "../pages/MediaPage.vue";
import SuperadminPage from "../pages/SuperadminPage.vue";
import UsersPage from "../pages/UsersPage.vue";
import { canUseRoute } from "../router";
import { useDashboardTools } from "../composables/useDashboardTools.js";
import { useI18n } from "../utils/i18n";
import "../tools.css";

const props = defineProps({
  initialRoute: { type: String, default: "demo" },
  language: { type: String, default: "en" }
});
const emit = defineEmits(["route-change", "back-profile", "session-expired"]);
const { t, setLang } = useI18n();
watch(() => props.language, setLang, { immediate: true });
const editor = ref(null);
function scrollToEditor() {
  nextTick(() => editor.value?.scrollTo({ top: 0, behavior: "instant" }));
}
const {
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
} = useDashboardTools({
  initialRoute: () => props.initialRoute,
  onRouteChange: (next) => emit("route-change", next),
  onSessionExpired: () => emit("session-expired"),
  scrollToEditor,
  t
});
const tools = computed(() => [
  { key: "demo", label: t.value.demo, icon: "✦" },
  { key: "api-keys", label: t.value.apiKeys, icon: "⌘" },
  { key: "books", label: t.value.books, icon: "▤" },
  { key: "users", label: t.value.users, icon: "◎" },
  { key: "media", label: t.value.media, icon: "◉" },
  { key: "admin", label: t.value.admin, icon: "⚙" },
  { key: "superadmin", label: t.value.superadmin, icon: "▦" }
].filter(tool => canUseRoute(tool.key, accessPoints.value)));
</script>

<template>
  <div class="dashboard-content">
    <nav class="dashboard-tools-nav" :aria-label="t.dashboardTools">
      <button class="back-profile" type="button" @click="emit('back-profile')">← {{ t.backToProfile }}</button>
      <button v-for="tool in tools" :key="tool.key" type="button" class="side-link" :class="{ active: route === tool.key }" :aria-current="route === tool.key ? 'page' : undefined" @click="go(tool.key)">
        <span aria-hidden="true">{{ tool.icon }}</span><span>{{ tool.label }}</span>
      </button>
    </nav>
    <div ref="editor" class="dashboard-main" :aria-busy="!profileLoaded && !loadingError">
      <div v-if="loadingError" role="alert" class="message error">
        {{ loadingError }} <button type="button" @click="loadProfile">{{ t.refresh }}</button>
      </div>
      <p v-else-if="!profileLoaded" role="status">{{ t.dashboardLoading }}</p>
      <ApiKeysPage
        v-if="route === 'api-keys' && accessPoints.includes('api-keys')"
        :t="t"
        :keys="keys"
        :output="output"
        :output-error="outputError"
        @create="createKey"
        @upgrade="upgradeKey"
        @revoke="revokeKey"
      />

      <DemoPage
        v-else-if="route === 'demo' && accessPoints.includes('profile')"
        :t="t"
        :access="demoAccess"
        :requests="demoRequests"
        :loading="demoLoading"
        :message="demoMessage"
        :error="demoError"
        :demo-url="demoUrl"
        @request="requestDemoAccess"
        @review="reviewDemoAccess"
        @refresh="loadDemoRequests"
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
        @set-demo="setBookDemoVisibility"
        @refresh="loadBooks"
      />

      <UsersPage
        v-else-if="route === 'users' && accessPoints.includes('admin')"
        :t="t"
        :users="users"
        :loading="usersLoading"
        :message="usersMessage"
        :error="usersError"
        @refresh="loadUsers"
      />

      <MediaPage
        v-else-if="route === 'media' && accessPoints.includes('media')"
        v-model:post-draft="postDraft"
        :t="t"
        :posts="posts"
        :editing-post-id="editingPostId"
        :message="mediaMessage"
        :error="mediaError"
        :saving="mediaSaving"
        :create-retry-pending="createRetryPending"
        @retry-create="retryCreate"
        :announcement-queued="announcementQueued"
        :email-preview="emailPreview"
        :preview-loading="previewLoading"
        :preview-error="previewError"
        @preview="previewEmail"
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

    </div>
  </div>
</template>
