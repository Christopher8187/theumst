<script setup>
import { computed, onMounted, ref } from "vue";
import { demoFetch } from "./api";
import { fetchGraphSlice, fetchSimilarKnowledge, isUnavailable } from "./services/studyApi";
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
const selectedId = ref(null);
const selectedNode = ref(null);
const originBookId = ref(null);
const mode = ref("text");
const sideMode = ref("graph");
const activeImage = ref(null);
const notes = ref([]);
const similarResults = ref([]);
const similarStatus = ref("idle");
const similarError = ref("");
const graphSlice = ref({ nodes: [], edges: [], graph_revision: null, focus_knowledge_id: null });
const graphStatus = ref("idle");
const graphError = ref("");
const graphQuery = ref({ bookId: null, focusId: null, ancestorDepth: 2, descendantDepth: 2 });
const summoning = ref(false);
const toast = ref("");
const loading = ref(true);
const error = ref("");
let toastTimer;
let graphRequest = 0;
let similarRequest = 0;
let selectionRequest = 0;
const studyCache = new Map();

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
  const cacheKey = String(bookId);
  let data = studyCache.get(cacheKey);
  if (!data) {
    data = await demoFetch(`/api/demo/grimoires/${bookId}/knowledge`);
    studyCache.set(cacheKey, data);
  }
  selectedBook.value = { ...selectedBook.value, ...data.book };
  nodes.value = data.knowledge;
  const firstExerciseId = mode.value === "questions"
    ? data.knowledge.find(node => node.type === "exercise")?.knowledge_id
    : null;
  selectedId.value = targetId || firstExerciseId || data.current_knowledge_id || data.knowledge[0]?.knowledge_id;
  selectedNode.value = null;
  if (selectedId.value) await selectNode(selectedId.value, false);
}

async function loadFocusedGraph(bookId, knowledgeId, options = {}) {
  const request = ++graphRequest;
  const ancestorDepth = Math.max(1, Math.min(4, Number(options.ancestorDepth) || 2));
  const descendantDepth = Math.max(1, Math.min(4, Number(options.descendantDepth) || 2));
  graphQuery.value = { bookId, focusId: knowledgeId, ancestorDepth, descendantDepth };
  graphStatus.value = "loading";
  graphError.value = "";
  try {
    const graph = await fetchGraphSlice(bookId, knowledgeId, { ancestorDepth, descendantDepth });
    if (request !== graphRequest) return;
    graphSlice.value = graph;
    graphStatus.value = graph.nodes.length ? "ready" : "empty";
  } catch (reason) {
    if (request !== graphRequest) return;
    graphSlice.value = { nodes: [], edges: [], graph_revision: null, focus_knowledge_id: knowledgeId };
    graphStatus.value = isUnavailable(reason) ? "unavailable" : "error";
    graphError.value = reason?.message || t.value.graphError;
  }
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
  view.value = "study";
}

async function selectNode(id, persist = true, graphOptions = {}) {
  const request = ++selectionRequest;
  if (selectedId.value !== id && ["image", "similar"].includes(sideMode.value)) closeSide();
  if (selectedNode.value?.knowledge_id !== id) selectedNode.value = null;
  selectedId.value = id;
  if (selectedBook.value?.grimoire_id) {
    void loadFocusedGraph(selectedBook.value.grimoire_id, id, graphOptions);
    const detail = await demoFetch(`/api/demo/grimoires/${selectedBook.value.grimoire_id}/knowledge/${id}`);
    if (request !== selectionRequest) return;
    const compact = nodes.value.find(node => node.knowledge_id === id) || {};
    selectedNode.value = { ...compact, ...detail.knowledge };
  }
  if (persist && selectedBook.value?.grimoire_id) {
    await demoFetch(`/api/demo/grimoires/${selectedBook.value.grimoire_id}/state`, {
      method: "PUT", body: JSON.stringify({ knowledge_id: id })
    });
    const cached = studyCache.get(String(selectedBook.value.grimoire_id));
    if (cached) cached.current_knowledge_id = id;
  }
  if (sideMode.value === "notes") await loadAttachedNotes();
}

function retryGraph() {
  const query = graphQuery.value;
  if (query.bookId == null || query.focusId == null) return;
  void loadFocusedGraph(query.bookId, query.focusId, query);
}

async function expandGraph({ knowledgeId, direction } = {}) {
  if (knowledgeId == null) return;
  const graphOptions = direction === "ancestors"
    ? { ancestorDepth: 4, descendantDepth: 2 }
    : { ancestorDepth: 2, descendantDepth: 4 };
  await selectNode(knowledgeId, true, graphOptions);
}

function openImage(image) {
  activeImage.value = image;
  sideMode.value = "image";
}

function closeSide() {
  similarRequest += 1;
  similarResults.value = [];
  similarStatus.value = "idle";
  similarError.value = "";
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
  if (name === "similar") {
    const sourceId = selectedId.value;
    const request = ++similarRequest;
    sideMode.value = "similar";
    similarResults.value = [];
    similarError.value = "";
    if (sourceId == null) {
      similarStatus.value = "idle";
      return;
    }
    similarStatus.value = "loading";
    try {
      const data = await fetchSimilarKnowledge(sourceId, { k: 10 });
      if (request !== similarRequest) return;
      similarResults.value = data.results;
      similarStatus.value = data.results.length ? "results" : "empty";
    } catch (reason) {
      if (request !== similarRequest) return;
      similarResults.value = [];
      similarStatus.value = isUnavailable(reason) ? "unavailable" : "error";
      similarError.value = reason?.message || t.value.similarError;
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

async function openSimilarResult(result) {
  const currentBookId = selectedBook.value?.grimoire_id;
  closeSide();
  if (String(result.grimoire_id) === String(currentBookId)) {
    await selectNode(result.knowledge_id);
    return;
  }
  originBookId.value = originBookId.value || currentBookId;
  const data = await demoFetch(`/api/demo/books/${result.grimoire_id}`);
  selectedBook.value = data.book;
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
  if (view.value === "study" || view.value === "notes") { view.value = "realm"; closeSide(); return; }
  view.value = "library";
}

onMounted(async () => {
  try {
    await loadBooks();
  } catch (reason) { error.value = reason.message; }
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
      <StudyView v-else-if="view === 'study'" :t="t" :book="selectedBook" :nodes="nodes" :selected-id="selectedId" :selected-node="selectedNode" :mode="mode" :side-mode="sideMode" :active-image="activeImage" :notes="notes" :similar-results="similarResults" :similar-status="similarStatus" :similar-error="similarError" :graph="graphSlice" :graph-status="graphStatus" :graph-error="graphError" :origin-book-id="originBookId" @select="selectNode" @retry-graph="retryGraph" @expand-graph="expandGraph" @soon="comingSoon" @action="action" @close-side="closeSide" @open-image="openImage" @save-note="saveNote" @notes-page="loadAllNotes().then(() => view = 'notes')" @open-result="openSimilarResult" @return-origin="returnOrigin" @move="moveExercise" @done="markDone" />
      <NotesDesk v-else-if="view === 'notes'" :t="t" :notes="notes" :grimoire-id="selectedBook?.grimoire_id" @save="saveNote" @delete="deleteNote" />
    </main>
    <Transition name="toast"><div v-if="toast" class="demo-toast"><span>✦</span>{{ toast }}</div></Transition>
  </div>
</template>
