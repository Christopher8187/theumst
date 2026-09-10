<script setup>
import { computed, onMounted, onBeforeUnmount, provide, ref, watch } from "vue";
import { demoFetch } from "./api";
import {
  fetchGraphSlice,
  fetchSimilarKnowledge,
  isUnavailable,
} from "./services/studyApi";
import { languageOptions, useDemoI18n } from "./i18n";
import { useNoteGuard } from "./composables/useNoteGuard";
import NoteDecision from "./components/NoteDecision.vue";
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
const sections = ref([]);
const originPosition = ref(null);
const history = ref([]);
const availability = ref(null);
let availabilityTimer;
let availabilityRequest = 0;
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
const discoveryKind = ref("similar");
const graphSlice = ref({
  nodes: [],
  edges: [],
  graph_revision: null,
  focus_knowledge_id: null,
});
const graphStatus = ref("idle");
const graphError = ref("");
const graphQuery = ref({
  bookId: null,
  focusId: null,
  ancestorDepth: 2,
  descendantDepth: 2,
});
const summoning = ref(false);
const toast = ref("");
const loading = ref(true);
const error = ref("");
let toastTimer;
let graphRequest = 0;
let similarRequest = 0;
let selectionRequest = 0;
const studyCache = new Map();
const guard = useNoteGuard(apiError);
const actionBusy = computed(() => guard.running.value || !!guard.editor.value?.saving());
let actionFocus = null;
provide("actionFocus", () => actionFocus);
provide("actionBusy", actionBusy);
watch(actionBusy, (busy) => {
  if (busy) actionFocus = document.activeElement;
}, { flush: "sync" });
watch(actionBusy, (busy) => {
  if (!busy && actionFocus?.isConnected) actionFocus.focus();
}, { flush: "post" });
provide("noteGuard", guard);
provide("saveNote", saveNote);
provide("apiError", apiError);
provide("deleteNote", deleteNote);
const run = (fn, ...args) => guard.run(() => fn(...args));
function captureExit(event) {
  const anchor = event.target.closest("a[href]");
  if (anchor && guard.editor.value?.dirty()) {
    event.preventDefault();
    run(() => {
      window.location.href = anchor.href;
    });
  }
}
function beforeUnload(event) {
  if (guard.editor.value?.dirty()) {
    event.preventDefault();
    event.returnValue = "";
  }
}

function apiError(reason) {
  notify(t.value.actionFailed);
}

const filteredBooks = computed(() => {
  const needle = query.value.toLowerCase().trim();
  return books.value.filter(
    (book) => !needle || book.title.toLowerCase().includes(needle),
  );
});
const filteredGrimoires = computed(() => {
  const needle = grimoireQuery.value.toLowerCase().trim();
  return grimoires.value.filter(
    (book) => !needle || book.title.toLowerCase().includes(needle),
  );
});
const showBack = computed(() => !["library", "realm"].includes(view.value));
const showMain = computed(() => view.value !== "library");

function notify(message) {
  toast.value = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
  }, 2600);
}

function comingSoon(kind) {
  notify(
    kind === "sound"
      ? t.value.soundSoon
      : kind === "prompt"
        ? t.value.promptSoon
        : kind === "project"
          ? t.value.projectSoon
          : t.value.comingSoon,
  );
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
    await demoFetch(
      `/api/demo/grimoires/${selectedBook.value.grimoire_id}/summon`,
      { method: "POST" },
    );
    selectedBook.value.summoned = true;
    notify(t.value.summoned);
    setTimeout(() => {
      summoning.value = false;
      view.value = "realm";
    }, 720);
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
  await demoFetch(`/api/demo/grimoires/${book.grimoire_id}/summon`, {
    method: "POST",
  });
  view.value = "realm";
}

async function loadStudy(
  bookId = selectedBook.value.grimoire_id,
  targetId = null,
) {
  const cacheKey = String(bookId);
  const data = await demoFetch(`/api/demo/grimoires/${bookId}/knowledge`);
  studyCache.set(cacheKey, data);
  sections.value = data.sections || [];
  selectedBook.value = { ...selectedBook.value, ...data.book };
  nodes.value = data.knowledge;
  const firstExerciseId =
    mode.value === "questions"
      ? data.knowledge.find((node) => node.type === "exercise")?.knowledge_id
      : null;
  const saved =
    mode.value === "questions"
      ? data.questions_knowledge_id
      : data.current_knowledge_id;
  selectedId.value =
    targetId || saved || firstExerciseId || data.knowledge[0]?.knowledge_id;
  if (
    selectedId.value &&
    !data.knowledge.some((n) => n.knowledge_id === selectedId.value)
  ) {
    notify(t.value.savedPositionUnavailable);
    selectedId.value = firstExerciseId || data.knowledge[0]?.knowledge_id;
  }
  selectedNode.value = null;
  if (selectedId.value)
    await selectNode(
      selectedId.value,
      !!targetId && selectedId.value === targetId,
      { recordHistory: false },
    );
}

async function loadFocusedGraph(bookId, knowledgeId, options = {}) {
  const request = ++graphRequest;
  const ancestorDepth = Math.max(
    1,
    Math.min(4, Number(options.ancestorDepth) || 2),
  );
  const descendantDepth = Math.max(
    1,
    Math.min(4, Number(options.descendantDepth) || 2),
  );
  graphQuery.value = {
    bookId,
    focusId: knowledgeId,
    ancestorDepth,
    descendantDepth,
  };
  graphStatus.value = "loading";
  graphError.value = "";
  try {
    const graph = await fetchGraphSlice(bookId, knowledgeId, {
      ancestorDepth,
      descendantDepth,
    });
    if (request !== graphRequest) return;
    graphSlice.value = graph;
    graphStatus.value = graph.nodes.length ? "ready" : "empty";
  } catch (reason) {
    if (request !== graphRequest) return;
    graphSlice.value = {
      nodes: [],
      edges: [],
      graph_revision: null,
      focus_knowledge_id: knowledgeId,
    };
    graphStatus.value = isUnavailable(reason) ? "unavailable" : "error";
    graphError.value = reason?.message || t.value.graphError;
  }
}

async function openRealm(realm) {
  if (["expand", "review", "preview", "advice", "progress"].includes(realm))
    return comingSoon();
  if (realm === "notes") {
    await loadAllNotes();
    view.value = "notes";
    return;
  }
  originBookId.value = selectedBook.value.grimoire_id;
  originPosition.value = null;
  history.value = [];
  mode.value = realm === "questions" ? "questions" : "text";
  sideMode.value = "graph";
  await loadStudy();
  view.value = "study";
}

async function selectNode(id, persist = true, graphOptions = {}) {
  const request = ++selectionRequest;
  if (selectedId.value !== id) {
    if (persist && graphOptions.recordHistory !== false && selectedId.value)
      history.value.push({
        bookId: selectedBook.value.grimoire_id,
        id: selectedId.value,
        mode: mode.value,
      });
    closeSide();
  }
  if (selectedNode.value?.knowledge_id !== id) selectedNode.value = null;
  selectedId.value = id;
  if (selectedBook.value?.grimoire_id) {
    void loadFocusedGraph(selectedBook.value.grimoire_id, id, graphOptions);
    const detail = await demoFetch(
      `/api/demo/grimoires/${selectedBook.value.grimoire_id}/knowledge/${id}`,
    );
    if (request !== selectionRequest) return;
    const compact = nodes.value.find((node) => node.knowledge_id === id) || {};
    selectedNode.value = {
      ...compact,
      ...detail.knowledge,
      completed: compact.completed ?? detail.knowledge.completed,
    };
  }
  if (persist && selectedBook.value?.grimoire_id) {
    await demoFetch(
      `/api/demo/grimoires/${selectedBook.value.grimoire_id}/state`,
      {
        method: "PUT",
        body: JSON.stringify({ knowledge_id: id, realm: mode.value }),
      },
    );
    const cached = studyCache.get(String(selectedBook.value.grimoire_id));
    if (cached)
      cached[
        mode.value === "questions"
          ? "questions_knowledge_id"
          : "current_knowledge_id"
      ] = id;
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
  const graphOptions =
    direction === "ancestors"
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
  const data = await demoFetch(
    `/api/demo/notes?knowledge_id=${selectedId.value}`,
  );
  notes.value = data.notes;
}

async function loadAllNotes() {
  const data = await demoFetch("/api/demo/notes");
  notes.value = data.notes;
}

async function saveNote(note) {
  const path = note.id ? `/api/demo/notes/${note.id}` : "/api/demo/notes";
  const result = await demoFetch(path, {
    method: note.id ? "PUT" : "POST",
    body: JSON.stringify({
      grimoire_id: note.grimoire_id,
      knowledge_id: note.knowledge_id,
      note_type: note.note_type,
      tag: note.tag,
      content: note.content,
    }),
  });
  notify(t.value.saved);
  if (view.value === "notes") await loadAllNotes();
  else await loadAttachedNotes();
  return result;
}

async function deleteNote(note) {
  await demoFetch(`/api/demo/notes/${note.demo_note_id}`, { method: "DELETE" });
  await loadAllNotes();
}

async function action(name) {
  if (name === "project") return comingSoon("project");
  if (name === "notes") {
    await loadAttachedNotes();
    sideMode.value = "notes";
    return;
  }
  if (["similar", "crystallize"].includes(name)) {
    discoveryKind.value = name;
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
      const data =
        name === "crystallize"
          ? await demoFetch(`/api/demo/crystallize/${sourceId}`)
          : await fetchSimilarKnowledge(sourceId, { k: 10 });
      if (request !== similarRequest) return;
      similarResults.value = data.results;
      if (data.processing_faults) notify(t.value.projectionFault);
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
    const currentIndex = nodes.value.findIndex(
      (node) => node.knowledge_id === selectedId.value,
    );
    const exercise = nodes.value
      .slice(currentIndex + 1)
      .find((node) => node.type === "exercise" && !node.completed);
    if (exercise) {
      history.value.push({
        bookId: selectedBook.value.grimoire_id,
        id: selectedId.value,
        mode: mode.value,
      });
      mode.value = "questions";
      sideMode.value = "graph";
      await selectNode(exercise.knowledge_id, true, { recordHistory: false });
    } else notify(t.value.noExerciseAhead);
    return;
  }
  if (name === "book") {
    mode.value = "text";
    sideMode.value = "graph";
    await loadStudy();
  }
}

async function openSimilarResult(result) {
  const currentBookId = selectedBook.value?.grimoire_id;
  closeSide();
  if (String(result.grimoire_id) === String(currentBookId)) {
    await selectNode(result.knowledge_id);
    return;
  }
  if (!originPosition.value)
    originPosition.value = {
      bookId: currentBookId,
      id: selectedId.value,
      mode: mode.value,
    };
  history.value.push({
    bookId: currentBookId,
    id: selectedId.value,
    mode: mode.value,
  });
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
  mode.value = originPosition.value?.mode || mode.value;
  await loadStudy(id, originPosition.value?.id);
  originPosition.value = null;
}

async function markDone(node) {
  const data = await demoFetch(`/api/demo/progress/${node.knowledge_id}`, {
    method: "PUT",
    body: JSON.stringify({ completed: !node.completed }),
  });
  node.completed = data.progress.completed;
  if (selectedNode.value?.knowledge_id === node.knowledge_id)
    selectedNode.value.completed = data.progress.completed;
  const compact = nodes.value.find(
    (item) => item.knowledge_id === node.knowledge_id,
  );
  if (compact) compact.completed = data.progress.completed;
  const graphNode = graphSlice.value.nodes?.find(
    (n) => n.knowledge_id === node.knowledge_id,
  );
  if (graphNode) graphNode.completed = data.progress.completed;
}

async function moveExercise(delta) {
  const exercises = nodes.value.filter((node) => node.type === "exercise");
  const current = exercises.findIndex(
    (node) => node.knowledge_id === selectedId.value,
  );
  const target =
    exercises[Math.max(0, Math.min(exercises.length - 1, current + delta))];
  if (target) await selectNode(target.knowledge_id);
}

function mainMenu() {
  view.value = "library";
  selectedNode.value = null;
  closeSide();
}
async function back() {
  if (view.value === "detail" || view.value === "grimoires") return mainMenu();
  if (
    view.value === "study" &&
    originBookId.value &&
    selectedBook.value?.grimoire_id !== originBookId.value
  ) {
    await returnOrigin();
    return;
  }
  if (view.value === "study" || view.value === "notes") {
    view.value = "realm";
    closeSide();
    return;
  }
  view.value = "library";
}

async function continueReading() {
  const at = nodes.value.findIndex((n) => n.knowledge_id === selectedId.value);
  if (at >= 0 && at < nodes.value.length - 1)
    await selectNode(nodes.value[at + 1].knowledge_id);
  else notify(t.value.endOfGrimoire);
}
async function backObject() {
  const previous = history.value.pop();
  if (!previous) return;
  mode.value = previous.mode;
  if (previous.bookId === selectedBook.value.grimoire_id)
    await selectNode(previous.id, true, { recordHistory: false });
  else await loadStudy(previous.bookId, previous.id);
}
async function notesPage() {
  await loadAllNotes();
  view.value = "notes";
}
async function checkAvailability() {
  if (view.value !== "study" || !selectedBook.value) return;
  const request = ++availabilityRequest;
  const checkedBookId = selectedBook.value.grimoire_id,
    checkedOriginId = originBookId.value;
  try {
    const data = await demoFetch("/api/demo/books");
    if (
      request !== availabilityRequest ||
      view.value !== "study" ||
      selectedBook.value?.grimoire_id !== checkedBookId ||
      originBookId.value !== checkedOriginId
    )
      return;
    const ids = new Set(data.books.map((b) => String(b.grimoire_id)));
    const base = ids.has(String(selectedBook.value.grimoire_id));
    const origin = ids.has(String(originBookId.value));
    if (!base) {
      selectedBook.value = { grimoire_id: selectedBook.value.grimoire_id };
      selectedNode.value = null;
      nodes.value = [];
      sections.value = [];
      graphSlice.value = { nodes: [], edges: [] };
      activeImage.value = null;
      similarResults.value = [];
      studyCache.clear();
      selectionRequest++;
      graphRequest++;
      similarRequest++;
    }
    if (!base || !origin) availability.value = { base, origin };
  } catch (reason) {
    notify(t.value.availabilityFailed);
  }
}
async function exitUnavailable() {
  availabilityRequest++;
  view.value = "grimoires";
  availability.value = null;
  selectedNode.value = null;
  nodes.value = [];
  closeSide();
  await loadGrimoires();
}
function stayAvailable() {
  availabilityRequest++;
  originBookId.value = selectedBook.value.grimoire_id;
  originPosition.value = null;
  availability.value = null;
}
onBeforeUnmount(() => {
  clearInterval(availabilityTimer);
  window.removeEventListener("focus", checkAvailability);
  window.removeEventListener("beforeunload", beforeUnload);
});

onMounted(async () => {
  availabilityTimer = setInterval(checkAvailability, 15000);
  window.addEventListener("focus", checkAvailability);
  window.addEventListener("beforeunload", beforeUnload);
  try {
    await loadBooks();
  } catch (reason) {
    error.value = reason.message;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="demo-shell" @click.capture="captureExit">
    <SideRail
      :inert="!!guard.pending.value || !!availability || guard.running.value || guard.editor.value?.saving()"
      :t="t"
      :show-main="showMain"
      :show-back="showBack"
      @main="run(mainMenu, $event)"
      @back="run(back, $event)"
    />
    <main
      class="demo-main"
      :inert="!!guard.pending.value || !!availability || guard.running.value || guard.editor.value?.saving()"
      :aria-busy="guard.running.value || guard.editor.value?.saving()"
    >
      <div class="demo-utility">
        <label
          >{{ t.language
          }}<select :value="lang" @change="setLang($event.target.value)">
            <option
              v-for="option in languageOptions"
              :key="option[0]"
              :value="option[0]"
            >
              {{ option[1] }}
            </option>
          </select></label
        >
        <span>{{ t.version }}</span>
      </div>
      <div v-if="loading" class="full-loader">
        <span></span>
        <p>{{ t.loadingLibrary }}</p>
      </div>
      <div v-else-if="error" class="fatal-error">
        <h1>{{ t.demoUnavailable }}</h1>
        <p>{{ error }}</p>
        <a href="/dashboard/demo/">{{ t.returnDashboard }}</a>
      </div>
      <LibraryView
        v-else-if="view === 'library'"
        v-model:query="query"
        :t="t"
        :books="filteredBooks"
        @open="run(openBook, $event)"
        @grimoires="run(loadGrimoires, $event)"
        @soon="comingSoon"
      />
      <BookDetail
        v-else-if="view === 'detail'"
        :t="t"
        :book="selectedBook"
        :contents="contents"
        :summoning="summoning"
        @summon="summon"
      />
      <GrimoireLibrary
        v-else-if="view === 'grimoires'"
        v-model:query="grimoireQuery"
        :t="t"
        :grimoires="filteredGrimoires"
        @open="run(openRealmBook, $event)"
      />
      <RealmRouter
        v-else-if="view === 'realm'"
        :t="t"
        :book="selectedBook"
        @realm="run(openRealm, $event)"
        @grimoires="run(loadGrimoires, $event)"
      />
      <StudyView
        v-else-if="view === 'study'"
        :t="t"
        :book="selectedBook"
        :nodes="nodes"
        :sections="sections"
        :can-back="history.length > 0"
        :selected-id="selectedId"
        :selected-node="selectedNode"
        :mode="mode"
        :side-mode="sideMode"
        :active-image="activeImage"
        :notes="notes"
        :similar-results="similarResults"
        :similar-status="similarStatus"
        :similar-error="similarError"
        :discovery-kind="discoveryKind"
        :graph="graphSlice"
        :graph-status="graphStatus"
        :graph-error="graphError"
        :origin-book-id="originBookId"
        @select="run(selectNode, $event)"
        @continue="run(continueReading)"
        @back-object="run(backObject)"
        @retry-graph="retryGraph"
        @expand-graph="expandGraph"
        @soon="comingSoon"
        @action="run(action, $event)"
        @close-side="run(closeSide, $event)"
        @open-image="run(openImage, $event)"
        @save-note="saveNote"
        @notes-page="run(notesPage)"
        @open-result="run(openSimilarResult, $event)"
        @return-origin="run(returnOrigin, $event)"
        @move="run(moveExercise, $event)"
        @done="run(markDone, $event)"
      />
      <NotesDesk
        v-else-if="view === 'notes'"
        :t="t"
        :notes="notes"
        :grimoire-id="selectedBook?.grimoire_id"
        @save="saveNote"
        @delete="deleteNote"
      />
    </main>
    <NoteDecision :t="t" :guard="guard" />
    <div v-if="availability" class="availability-backdrop">
      <section
        role="dialog"
        aria-modal="true"
        :aria-label="t.sourceUnavailable"
      >
        <h2>{{ t.sourceUnavailable }}</h2>
        <p>{{ availability.base ? t.originUnavailable : t.baseUnavailable }}</p>
        <button type="button" @click="run(exitUnavailable)">
          {{ t.confirmExit }}</button
        ><button v-if="availability.base" type="button" @click="stayAvailable">
          {{ t.stayBase }}
        </button>
      </section>
    </div>
    <Transition name="toast"
      ><div v-if="toast" class="demo-toast">
        <span>✦</span>{{ toast }}
      </div></Transition
    >
  </div>
</template>
