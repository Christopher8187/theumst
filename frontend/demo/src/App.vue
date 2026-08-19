<script setup>
import { computed, onMounted, ref } from "vue";
import { demoFetch } from "./api";
import { languageOptions, useDemoI18n } from "./i18n";
import SideRail from "./components/SideRail.vue";
import LibraryView from "./components/LibraryView.vue";
import BookDetail from "./components/BookDetail.vue";
import GrimoireLibrary from "./components/GrimoireLibrary.vue";
import RealmRouter from "./components/RealmRouter.vue";
import StudyView from "./components/StudyView.vue";
import NotesDesk from "./components/NotesDesk.vue";

const { lang, t, setLang } = useDemoI18n();
const view = ref("library");
const books = ref([]);
const grimoires = ref([]);
const query = ref("");
const grimoireQuery = ref("");
const selectedBook = ref(null);
const contents = ref([]);
const nodes = ref([]);
const relationCounts = ref({});
const selectedId = ref(null);
const selectedNode = ref(null);
const originBookId = ref(null);
const mode = ref("text");
const sideMode = ref("graph");
const activeImage = ref(null);
const notes = ref([]);
const searchResults = ref([]);
const searchLoading = ref(false);
const summoning = ref(false);
const toast = ref("");
const loading = ref(true);
const error = ref("");
let toastTimer;

function apiError(reason) {
  error.value = reason?.message || "The demo could not complete that action.";
  notify(error.value);
}

const filteredBooks = computed(() => {
  const needle = query.value.toLowerCase().trim();
  return books.value.filter(book => !needle || book.title.toLowerCase().includes(needle));
});
const filteredGrimoires = computed(() => {
  const needle = grimoireQuery.value.toLowerCase().trim();
  return grimoires.value.filter(book => !needle || book.title.toLowerCase().includes(needle));
});
const showBack = computed(() => !["library", "realm"].includes(view.value));
const showMain = computed(() => view.value !== "library");

function notify(message) {
  toast.value = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.value = ""; }, 2600);
}

function comingSoon(kind) {
  notify(kind === "sound" ? t.value.soundSoon : kind === "prompt" ? t.value.promptSoon : kind === "project" ? t.value.projectSoon : t.value.comingSoon);
}

async function loadBooks() {
  const data = await demoFetch("/api/demo/books");
  books.value = data.books;
}

async function openBook(book) {
  const data = await demoFetch(`/api/demo/books/${book.grimoire_id}`);
  selectedBook.value = data.book;
  contents.value = data.contents;
  view.value = "detail";
}

async function summon() {
  summoning.value = true;
  try {
    await demoFetch(`/api/demo/grimoires/${selectedBook.value.grimoire_id}/summon`, { method: "POST" });
    selectedBook.value.summoned = true;
    notify(t.value.summoned);
    setTimeout(() => { summoning.value = false; view.value = "realm"; }, 720);
  } catch (reason) {
    summoning.value = false;
    apiError(reason);
  }
}

async function loadGrimoires() {
  const data = await demoFetch("/api/demo/grimoires");
  grimoires.value = data.grimoires;
  view.value = "grimoires";
}

async function openRealmBook(book) {
  selectedBook.value = book;
  await demoFetch(`/api/demo/grimoires/${book.grimoire_id}/summon`, { method: "POST" });
  view.value = "realm";
}

async function loadStudy(bookId = selectedBook.value.grimoire_id, targetId = null) {
  const data = await demoFetch(`/api/demo/grimoires/${bookId}/knowledge`);
  selectedBook.value = { ...selectedBook.value, ...data.book };
  nodes.value = data.knowledge;
  relationCounts.value = data.relation_counts || {};
  selectedId.value = targetId || data.current_knowledge_id || data.knowledge[0]?.knowledge_id;
  selectedNode.value = null;
  if (selectedId.value) await selectNode(selectedId.value, false);
}

async function openRealm(realm) {
  if (["expand", "review", "preview", "advice", "progress"].includes(realm)) return comingSoon();
  if (realm === "notes") {
    await loadAllNotes();
    view.value = "notes";
    return;
  }
  originBookId.value = selectedBook.value.grimoire_id;
  mode.value = realm === "questions" ? "questions" : "text";
  sideMode.value = "graph";
  await loadStudy();
  if (mode.value === "questions") {
    const exercise = nodes.value.find(node => node.type === "exercise");
    if (exercise) await selectNode(exercise.knowledge_id);
  }
  view.value = "study";
}

async function selectNode(id, persist = true) {
  if (selectedId.value !== id && sideMode.value === "image") closeSide();
  if (selectedNode.value?.knowledge_id !== id) selectedNode.value = null;
  selectedId.value = id;
  if (selectedBook.value?.grimoire_id) {
    const detail = await demoFetch(`/api/demo/grimoires/${selectedBook.value.grimoire_id}/knowledge/${id}`);
    const compact = nodes.value.find(node => node.knowledge_id === id) || {};
    selectedNode.value = { ...compact, ...detail.knowledge };
  }
  if (persist && selectedBook.value?.grimoire_id) {
    await demoFetch(`/api/demo/grimoires/${selectedBook.value.grimoire_id}/state`, {
      method: "PUT", body: JSON.stringify({ knowledge_id: id })
    });
  }
  if (sideMode.value === "notes") await loadAttachedNotes();
}

function openImage(image) {
  activeImage.value = image;
  sideMode.value = "image";
}

function closeSide() {
  activeImage.value = null;
  sideMode.value = "graph";
}

async function loadAttachedNotes() {
  if (!selectedId.value) return;
  const data = await demoFetch(`/api/demo/notes?knowledge_id=${selectedId.value}`);
  notes.value = data.notes;
}

async function loadAllNotes() {
  const data = await demoFetch("/api/demo/notes");
  notes.value = data.notes;
}

async function saveNote(note) {
  const path = note.id ? `/api/demo/notes/${note.id}` : "/api/demo/notes";
  await demoFetch(path, { method: note.id ? "PUT" : "POST", body: JSON.stringify({
    grimoire_id: note.grimoire_id, knowledge_id: note.knowledge_id,
    note_type: note.note_type, tag: note.tag, content: note.content
  }) });
  notify(t.value.saved);
  if (view.value === "notes") await loadAllNotes(); else await loadAttachedNotes();
}

async function deleteNote(note) {
  await demoFetch(`/api/demo/notes/${note.demo_note_id}`, { method: "DELETE" });
  await loadAllNotes();
}

async function action(name) {
  if (name === "project") return comingSoon("project");
  if (name === "notes") {
    sideMode.value = "notes";
    await loadAttachedNotes();
    return;
  }
  if (name === "crystallize") {
    sideMode.value = "search";
    searchLoading.value = true;
    try {
      const data = await demoFetch(`/api/demo/crystallize/${selectedId.value}`);
      searchResults.value = data.results;
    } catch (reason) {
      searchResults.value = [];
      apiError(reason);
    } finally {
      searchLoading.value = false;
    }
    return;
  }
  if (name === "train") {
    const currentIndex = nodes.value.findIndex(node => node.knowledge_id === selectedId.value);
    const exercise = nodes.value.slice(currentIndex + 1).find(node => node.type === "exercise" && !node.completed)
      || nodes.value.find(node => node.type === "exercise" && !node.completed)
      || nodes.value.find(node => node.type === "exercise");
    if (exercise) { mode.value = "questions"; sideMode.value = "graph"; await selectNode(exercise.knowledge_id); }
    return;
  }
  if (name === "book") {
    mode.value = "text";
    sideMode.value = "graph";
    const currentIndex = nodes.value.findIndex(node => node.knowledge_id === selectedId.value);
    const previousBookwork = [...nodes.value.slice(0, Math.max(currentIndex, 0))]
      .reverse()
      .find(node => node.type !== "exercise");
    const target = previousBookwork || nodes.value.find(node => node.type !== "exercise");
    if (target) await selectNode(target.knowledge_id);
  }
}

async function openSearchResult(result) {
  const original = originBookId.value || selectedBook.value.grimoire_id;
  originBookId.value = original;
  const data = await demoFetch(`/api/demo/books/${result.grimoire_id}`);
  selectedBook.value = data.book;
  sideMode.value = "graph";
  mode.value = "text";
  await loadStudy(result.grimoire_id, result.knowledge_id);
}

async function returnOrigin() {
  const id = originBookId.value;
  const data = await demoFetch(`/api/demo/books/${id}`);
  selectedBook.value = data.book;
  await loadStudy(id);
}

async function markDone(node) {
  const data = await demoFetch(`/api/demo/progress/${node.knowledge_id}`, {
    method: "PUT", body: JSON.stringify({ completed: !node.completed })
  });
  node.completed = data.progress.completed;
  const compact = nodes.value.find(item => item.knowledge_id === node.knowledge_id);
  if (compact) compact.completed = data.progress.completed;
}

async function moveExercise(delta) {
  const exercises = nodes.value.filter(node => node.type === "exercise");
  const current = exercises.findIndex(node => node.knowledge_id === selectedId.value);
  const target = exercises[Math.max(0, Math.min(exercises.length - 1, current + delta))];
  if (target) await selectNode(target.knowledge_id);
}

function mainMenu() { view.value = "library"; selectedNode.value = null; closeSide(); }
async function back() {
  if (view.value === "detail" || view.value === "grimoires") return mainMenu();
  if (view.value === "study" && originBookId.value && selectedBook.value?.grimoire_id !== originBookId.value) {
    await returnOrigin();
    return;
  }
  if (view.value === "study" || view.value === "notes") { view.value = "realm"; sideMode.value = "graph"; return; }
  view.value = "library";
}

onMounted(async () => {
  try { await loadBooks(); } catch (reason) { error.value = reason.message; }
  finally { loading.value = false; }
});
</script>

<template>
  <div class="demo-shell">
    <SideRail :t="t" :show-main="showMain" :show-back="showBack" @main="mainMenu" @back="back" />
    <main class="demo-main">
      <div class="demo-utility">
        <label>{{ t.language }}<select :value="lang" @change="setLang($event.target.value)"><option v-for="option in languageOptions" :key="option[0]" :value="option[0]">{{ option[1] }}</option></select></label>
        <span>{{ t.version }}</span>
      </div>
      <div v-if="loading" class="full-loader"><span></span><p>Summoning the library…</p></div>
      <div v-else-if="error" class="fatal-error"><h1>Demo unavailable</h1><p>{{ error }}</p><a href="/dashboard/demo/">Return to dashboard</a></div>
      <LibraryView v-else-if="view === 'library'" v-model:query="query" :t="t" :books="filteredBooks" @open="openBook" @grimoires="loadGrimoires" @soon="comingSoon" />
      <BookDetail v-else-if="view === 'detail'" :t="t" :book="selectedBook" :contents="contents" :summoning="summoning" @summon="summon" />
      <GrimoireLibrary v-else-if="view === 'grimoires'" v-model:query="grimoireQuery" :t="t" :grimoires="filteredGrimoires" @open="openRealmBook" />
      <RealmRouter v-else-if="view === 'realm'" :t="t" :book="selectedBook" @realm="openRealm" @grimoires="loadGrimoires" />
      <StudyView v-else-if="view === 'study'" :t="t" :book="selectedBook" :nodes="nodes" :relation-counts="relationCounts" :selected-id="selectedId" :selected-node="selectedNode" :mode="mode" :side-mode="sideMode" :active-image="activeImage" :notes="notes" :search-results="searchResults" :search-loading="searchLoading" :origin-book-id="originBookId" @select="selectNode" @soon="comingSoon" @action="action" @close-side="closeSide" @open-image="openImage" @save-note="saveNote" @notes-page="loadAllNotes().then(() => view = 'notes')" @open-result="openSearchResult" @return-origin="returnOrigin" @move="moveExercise" @done="markDone" />
      <NotesDesk v-else-if="view === 'notes'" :t="t" :notes="notes" :grimoire-id="selectedBook?.grimoire_id" @save="saveNote" @delete="deleteNote" />
    </main>
    <Transition name="toast"><div v-if="toast" class="demo-toast"><span>✦</span>{{ toast }}</div></Transition>
  </div>
</template>
