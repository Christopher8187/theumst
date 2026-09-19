import { computed, onMounted, onBeforeUnmount, provide, ref, toValue, watch } from 'vue';
import { demoFetch } from '../../api';
import { fetchGraphSlice, fetchSimilarKnowledge, isUnavailable } from '../../services/studyApi';
import { useNoteGuard } from '../../composables/useNoteGuard';
import { displayBook } from '../useGrimoireLibrary';
import { adjacentStudyNode, realmForNode } from './studyNavigation';

/** Persisted reader actions retained from the previous Demo, with the accepted realm navigation. */
export function useTextStudy(bookIdRef, tRef, onCompletion, initialModeRef = 'text', onExit = () => {}, initialNotes = false) {
const t = computed(() => toValue(tRef));
const view = ref("study");

const selectedBook = ref({ grimoire_id: Number(toValue(bookIdRef)), title: "" });

const sections = ref([]);
const originPosition = ref(null);

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

const toast = ref("");
const loading = ref(true);
const error = ref("");
let toastTimer;
let graphRequest = 0;
let similarRequest = 0;
let selectionRequest = 0;
const studyCache = new Map();
const guard = useNoteGuard(apiError);
const actionBusy = computed(() => loading.value || guard.running.value || guard.saving.value || !!guard.editor.value?.saving());
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
  notify(reason?.message || t.value.actionFailed);
}

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

async function loadStudy(
  bookId = selectedBook.value.grimoire_id,
  targetId = null,
) {
  const cacheKey = String(bookId);
  closeSide();
  const data = await demoFetch(`/api/demo/grimoires/${bookId}/knowledge`);
  studyCache.set(cacheKey, data);
  sections.value = data.sections || [];
  selectedBook.value = { ...selectedBook.value, ...data.book };
  nodes.value = data.knowledge;
  const saved =
    mode.value === "questions"
      ? data.questions_knowledge_id
      : data.current_knowledge_id;
  const eligible = data.knowledge.filter(node => realmForNode(node) === mode.value);
  const savedAvailable = eligible.some(node => node.knowledge_id === saved);
  if (!targetId && saved != null && !savedAvailable) notify(t.value.savedPositionUnavailable);
  const targetAvailable = data.knowledge.some(node => node.knowledge_id === targetId);
  selectedId.value = targetAvailable ? targetId : savedAvailable ? saved : eligible[0]?.knowledge_id;
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

async function selectNode(id, persist = true, graphOptions = {}) {
  const target = nodes.value.find(node => node.knowledge_id === Number(id));
  if (!target) return;
  id = target.knowledge_id;
  mode.value = realmForNode(target);
  const request = ++selectionRequest;
  if (selectedId.value !== id) {

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
  const noteId = note.id || note.demo_note_id;
  const path = noteId ? `/api/demo/notes/${noteId}` : "/api/demo/notes";
  const result = await demoFetch(path, {
    method: noteId ? "PUT" : "POST",
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

  if (name === "notes") {
    await loadAttachedNotes();
    sideMode.value = "notes";
    return;
  }
  if (["similar", "crystallize", "dependencies"].includes(name)) {
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
          : name === "dependencies" ? await demoFetch(`/api/demo/knowledge/${sourceId}/dependencies`)
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
  onCompletion(String(selectedBook.value.grimoire_id), nodes.value.filter(item => item.completed).length);
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

async function continueReading() {
  const next = adjacentStudyNode(nodes.value, selectedId.value, mode.value, 1);
  if (next) await selectNode(next.knowledge_id);
}
async function backObject() {
  const previous = adjacentStudyNode(nodes.value, selectedId.value, mode.value, -1);
  if (previous) await selectNode(previous.knowledge_id);
}
async function notesPage() {
  await loadAllNotes();
  view.value = "notes";
}
async function checkAvailability() {
  if (!["study", "notes"].includes(view.value) || !selectedBook.value) return;
  const request = ++availabilityRequest;
  const checkedBookId = selectedBook.value.grimoire_id,
    checkedOriginId = originBookId.value;
  try {
    const data = await demoFetch("/api/demo/books");
    if (
      request !== availabilityRequest ||
      !["study", "notes"].includes(view.value) ||
      selectedBook.value?.grimoire_id !== checkedBookId ||
      originBookId.value !== checkedOriginId
    )
      return;
    const ids = new Set(data.books.map((b) => String(b.grimoire_id)));
    const base = ids.has(String(selectedBook.value.grimoire_id));
    const origin = ids.has(String(originBookId.value));
    if (!base) {
      selectedBook.value = { grimoire_id: selectedBook.value.grimoire_id };
      notes.value = [];
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
  onExit();
}
function stayAvailable() {
  availabilityRequest++;
  originBookId.value = selectedBook.value.grimoire_id;
  originPosition.value = null;
  availability.value = null;
}
onBeforeUnmount(() => {
  selectionRequest++; graphRequest++; similarRequest++; availabilityRequest++;
  clearTimeout(toastTimer); clearInterval(availabilityTimer);
  window.removeEventListener("focus", checkAvailability);
  window.removeEventListener("beforeunload", beforeUnload);
});

onMounted(async () => {
  availabilityTimer = setInterval(checkAvailability, 15000);
  window.addEventListener("focus", checkAvailability);
  window.addEventListener("beforeunload", beforeUnload);
  try {
    await entrance();
  } catch (reason) {
    error.value = reason.message;
  } finally {
    loading.value = false;
  }
});

const book = computed(() => selectedBook.value);
const sampleBook = computed(() => displayBook({ ...selectedBook.value, knowledge_count: nodes.value.length,
  completed_count: nodes.value.filter(node => node.completed).length }, sections.value));
const showingAllNotes = computed(() => view.value === 'notes');
const canBack = computed(() => !!adjacentStudyNode(nodes.value, selectedId.value, mode.value, -1));
const canContinue = computed(() => !!adjacentStudyNode(nodes.value, selectedId.value, mode.value, 1));
async function entrance() {
  originBookId.value = Number(toValue(bookIdRef)); originPosition.value = null;
  mode.value = toValue(initialModeRef) || 'text'; view.value = 'study';
  await loadStudy(originBookId.value);
  if (toValue(initialNotes)) await notesPage();
}
watch([() => toValue(bookIdRef), () => toValue(initialModeRef)], ([nextBook, nextMode], [previousBook]) => {
  if (nextBook === previousBook && mode.value === (nextMode || 'text')) return;
  run(entrance);
});
return { book, sampleBook, nodes, sections, selectedId, selectedNode, mode, sideMode,
  notes, allNotes: notes, showingAllNotes, graph: graphSlice, graphStatus, graphError,
  similarResults, similarStatus, similarError, discoveryKind, originBookId, activeImage,
  canBack, canContinue, guard, actionBusy, toast, loading, error, availability,
  run, captureExit, select: selectNode, continueReading, backObject, action, closeSide,
  saveNote, deleteNote, notesPage, openResult: openSimilarResult, returnOrigin,
  moveExercise, markDone, openImage, comingSoon, exitUnavailable, stayAvailable, retryGraph };
}
