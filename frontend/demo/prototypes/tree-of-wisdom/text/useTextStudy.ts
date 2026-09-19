import { computed, inject, onBeforeUnmount, onMounted, provide, reactive, ref, shallowRef, toValue, watch, type InjectionKey, type MaybeRefOrGetter, type Ref } from 'vue';
import { useNoteGuard } from '../../../src/composables/useNoteGuard';
import { type SampleBook } from '../books';
import { createStudyFixtures, discoveryExamples, sampleBookIds, type StudyFixture, type StudyImage, type StudyMode, type StudyNode, type StudyResult } from './studyFixtures';
import { adjacentStudyNode, realmForNode } from './studyNavigation';

type SideMode = 'graph' | 'notes' | 'similar' | 'image';
type Position = { bookId: number; id: number; mode: StudyMode };
type NoteKind = 'attached' | 'scribble';
export interface LocalStudyNote {
  id?: number;
  demo_note_id?: number;
  grimoire_id: number | null;
  knowledge_id: number | null;
  note_type: NoteKind;
  tag: string;
  content: string;
  knowledge_label?: string;
  book_title?: string;
}
interface ReaderState {
  bookId: number;
  selectedId: number;
  mode: StudyMode;
  origin: Position | null;
}
interface TextStudySession {
  fixtures: Record<number, StudyFixture>;
  positions: Record<number, Partial<Record<StudyMode, number>>>;
  notes: Ref<LocalStudyNote[]>;
  nextNoteId: number;
}
const sessionKey: InjectionKey<TextStudySession> = Symbol('wisdom-text-study-session');

function createSession(seedBooks?: readonly SampleBook[]): TextStudySession {
  return { fixtures: reactive(createStudyFixtures(seedBooks)), positions: reactive({}), notes: ref([]), nextNoteId: 1 };
}

/** Call once in TreePrototype setup. State ends with that page instance. */
export function provideTextStudySession(seedBooks?: readonly SampleBook[]) {
  const session = createSession(seedBooks);
  provide(sessionKey, session);
  return session;
}

/** In-memory counterpart of App.vue's reader actions; the production views stay unchanged. */
export function useTextStudy(
  bookIdRef: MaybeRefOrGetter<string>,
  tRef: MaybeRefOrGetter<Record<string, string>>,
  onCompletion: (sampleBookId: string, completed: number) => void,
  initialModeRef: MaybeRefOrGetter<StudyMode | undefined> = 'text',
) {
  const session = inject(sessionKey, null) || createSession();
  const studyCase = typeof window === 'undefined' ? '' : new URLSearchParams(window.location?.search || '').get('studyCase') || '';
  const initialBookId = () => sampleBookIds[toValue(bookIdRef)] || 1;
  function savedPosition(bookId: number, mode: StudyMode) {
    const fixture = session.fixtures[bookId];
    return session.positions[bookId]?.[mode]
      || (mode === 'questions' ? fixture.nodes.find(node => node.type === 'exercise')?.knowledge_id : null)
      || fixture.nodes[0].knowledge_id;
  }
  function readerForEntrance() {
    const bookId = initialBookId(), mode = toValue(initialModeRef) || 'text';
    // Re-enter the requested book and realm, as the original Demo does. Only
    // positions, completion and writing survive leaving this reader instance.
    return reactive<ReaderState>({ bookId, selectedId: savedPosition(bookId, mode), mode, origin: null });
  }
  const reader = shallowRef(readerForEntrance());
  const fixture = computed(() => session.fixtures[reader.value.bookId]);
  const book = computed(() => fixture.value.book);
  const sampleBook = computed(() => fixture.value.sample);
  const nodes = computed(() => fixture.value.nodes);
  const sections = computed(() => fixture.value.sections);
  const selectedId = computed(() => reader.value.selectedId);
  const selectedNode = computed(() => nodes.value.find(node => node.knowledge_id === selectedId.value) || null);
  const mode = computed(() => reader.value.mode);
  const canBack = computed(() => !!adjacentStudyNode(nodes.value, selectedId.value, mode.value, -1));
  const canContinue = computed(() => !!adjacentStudyNode(nodes.value, selectedId.value, mode.value, 1));
  const originBookId = computed(() => reader.value.origin?.bookId || initialBookId());
  const sideMode = ref<SideMode>('graph');
  const activeImage = shallowRef<StudyImage | null>(null);
  const similarResults = ref<StudyResult[]>([]);
  const similarStatus = ref('idle');
  const similarError = ref('');
  const discoveryKind = ref('similar');
  const showingAllNotes = ref(false);
  const notes = computed(() => session.notes.value.filter(note => note.note_type === 'attached' && note.knowledge_id === selectedId.value));
  const allNotes = computed(() => session.notes.value);
  const graph = computed(() => ({ authored_dependencies: studyCase !== 'no-dependencies', nodes: nodes.value, edges: studyCase === 'no-dependencies' ? [] : fixture.value.edges, graph_revision: 'local-authored-examples-v1', focus_knowledge_id: selectedId.value }));
  const graphStatus = ref('ready'), graphError = ref('');
  const toast = ref('');
  const stub = ref<'sound' | 'prompt' | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;
  let focusBeforeAction: HTMLElement | null = null;
  const words = () => toValue(tRef);
  function notify(message: string) {
    clearTimeout(toastTimer); toast.value = message;
    toastTimer = setTimeout(() => { toast.value = ''; }, 4500);
  }
  function apiError(error: unknown) { notify(error instanceof Error ? error.message : words().error || 'The local action could not be completed.'); }
  const guard = useNoteGuard(apiError);
  const actionBusy = computed(() => guard.running.value || guard.saving.value || !!guard.editor.value?.saving());
  const run = <Args extends unknown[]>(operation: (...args: Args) => unknown, ...args: Args) => guard.run(() => operation(...args));
  provide('noteGuard', guard);
  provide('saveNote', saveNote);
  provide('deleteNote', deleteNote);
  provide('apiError', apiError);
  provide('actionBusy', actionBusy);
  provide('actionFocus', () => focusBeforeAction);
  watch(actionBusy, busy => { if (busy && typeof document !== 'undefined') focusBeforeAction = document.activeElement as HTMLElement | null; }, { flush: 'sync' });
  watch(actionBusy, busy => { if (!busy && focusBeforeAction?.isConnected) focusBeforeAction.focus(); }, { flush: 'post' });
  watch([() => toValue(bookIdRef), () => toValue(initialModeRef)], ([nextBook, nextMode], [previousBook]) => {
    // A selection can change realms in this same reader. The parent mirrors
    // that realm in the URL; its acknowledgement must not reset the position.
    if (nextBook === previousBook && reader.value.mode === (nextMode || 'text')) return;
    reader.value = readerForEntrance(); showingAllNotes.value = false; closeSide();
  });

  function currentPosition(): Position { return { bookId: reader.value.bookId, id: selectedId.value, mode: mode.value }; }
  function rememberPosition() {
    (session.positions[reader.value.bookId] ||= {})[mode.value] = selectedId.value;
  }
  function closeSide() {
    sideMode.value = 'graph'; activeImage.value = null;
    similarResults.value = []; similarStatus.value = 'idle'; similarError.value = '';
  }
  function restore(position: Position) {
    if (!session.fixtures[position.bookId]?.nodes.some(node => node.knowledge_id === position.id)) return;
    closeSide(); showingAllNotes.value = false;
    reader.value.bookId = position.bookId; reader.value.mode = position.mode; reader.value.selectedId = position.id;
    rememberPosition();
  }
  function select(id: number | string) {
    const target = nodes.value.find(node => node.knowledge_id === Number(id));
    if (!target || target.knowledge_id === selectedId.value) return;
    closeSide(); reader.value.mode = realmForNode(target); reader.value.selectedId = target.knowledge_id; rememberPosition();
  }
  function continueReading() {
    const next = adjacentStudyNode(nodes.value, selectedId.value, mode.value, 1);
    if (next) select(next.knowledge_id);
    else notify(words().endOfGrimoire || 'You have reached the end of this grimoire.');
  }
  function backObject() {
    const previous = adjacentStudyNode(nodes.value, selectedId.value, mode.value, -1);
    if (previous) select(previous.knowledge_id);
  }
  function action(name: string) {
    if (name === 'notes') { sideMode.value = 'notes'; return; }
    if (name === 'similar' || name === 'crystallize' || name === 'dependencies') {
      discoveryKind.value = name; sideMode.value = 'similar'; similarError.value = '';
      if (name === 'dependencies') {
        similarResults.value = selectedNode.value && studyCase !== 'no-dependencies'
          ? discoveryExamples(session.fixtures, selectedNode.value, name) : [];
        similarStatus.value = similarResults.value.length ? 'results' : 'empty';
        return;
      }
      if (['discovery-empty', 'discovery-error', 'discovery-unavailable', 'discovery-loading'].includes(studyCase)) {
        similarResults.value = []; similarStatus.value = studyCase.replace('discovery-', '');
        if (similarStatus.value === 'error') similarError.value = 'Local example of an unavailable discovery request.';
        return;
      }
      similarResults.value = selectedNode.value ? discoveryExamples(session.fixtures, selectedNode.value, name) : [];
      similarStatus.value = similarResults.value.length ? 'results' : 'empty';
      return;
    }
    if (name === 'train') {
      const current = nodes.value.findIndex(node => node.knowledge_id === selectedId.value);
      const next = nodes.value.slice(current + 1).find(node => node.type === 'exercise' && !node.completed);
      if (!next) { notify(words().noExerciseAhead || 'There are no unfinished exercises ahead.'); return; }
      closeSide(); reader.value.mode = 'questions'; reader.value.selectedId = next.knowledge_id; rememberPosition();
      return;
    }
    if (name === 'book') {
      restore({ bookId: reader.value.bookId, id: savedPosition(reader.value.bookId, 'text'), mode: 'text' });
    }
  }
  function openResult(result: Pick<StudyResult, 'grimoire_id' | 'knowledge_id'>) {
    const target = session.fixtures[result.grimoire_id]?.nodes.find(node => node.knowledge_id === result.knowledge_id);
    if (!target) return;
    if (result.grimoire_id === reader.value.bookId) { closeSide(); select(result.knowledge_id); return; }
    const previous = currentPosition();
    reader.value.origin ||= previous;
    restore({ bookId: result.grimoire_id, id: result.knowledge_id, mode: realmForNode(target) });
  }
  function returnOrigin() {
    const origin = reader.value.origin;
    if (!origin) return;
    // Keep the first departure available until the reader is entered afresh.
    restore(origin);
  }
  function moveExercise(delta: number) {
    const target = adjacentStudyNode(nodes.value, selectedId.value, 'questions', delta < 0 ? -1 : 1);
    if (target) select(target.knowledge_id);
  }
  function markDone(node: Pick<StudyNode, 'knowledge_id'>) {
    const target = nodes.value.find(item => item.knowledge_id === node.knowledge_id);
    if (!target) return;
    target.completed = !target.completed;
    const completed = nodes.value.filter(item => item.completed).length;
    fixture.value.sample.completed = completed;
    onCompletion(sampleBook.value.id, completed);
  }
  function openImage(image: StudyImage) { activeImage.value = image; sideMode.value = 'image'; }
  function notesPage() { showingAllNotes.value = true; closeSide(); }
  function returnFromNotes() { showingAllNotes.value = false; closeSide(); }
  async function saveNote(payload: LocalStudyNote) {
    if (studyCase === 'notes-save-error') throw new Error(words().localNoteSaveError || 'Local save-failure example: your draft has been kept.');
    const id = payload.id || payload.demo_note_id;
    const old = id ? session.notes.value.find(note => note.demo_note_id === id) : undefined;
    if (id && !old) throw new Error(words().noteUnavailable || 'This local note is no longer available.');
    const sourceBook = payload.grimoire_id ? session.fixtures[payload.grimoire_id] : undefined;
    const source = sourceBook?.nodes.find(node => node.knowledge_id === payload.knowledge_id);
    const note: LocalStudyNote = { demo_note_id: id || session.nextNoteId++, grimoire_id: payload.grimoire_id,
      knowledge_id: payload.note_type === 'attached' ? payload.knowledge_id : null, note_type: payload.note_type,
      tag: String(payload.tag || '').slice(0, 120), content: String(payload.content || ''), knowledge_label: source?.label, book_title: sourceBook?.book.title };
    if (old) session.notes.value = session.notes.value.map(item => item.demo_note_id === id ? note : item);
    else session.notes.value = [...session.notes.value, note];
    notify(words().saved || 'Saved for this visit.');
    return { note };
  }
  async function deleteNote(note: LocalStudyNote) {
    session.notes.value = session.notes.value.filter(item => item.demo_note_id !== note.demo_note_id);
  }
  function comingSoon(kind?: string) {
    if (kind === 'sound' || kind === 'prompt') {
      stub.value = kind;
      const message = words()[`${kind}Soon`];
      notify(message || words().comingSoon || 'This action will be designed in a later round.');
    }
    else notify(words().comingSoon || 'This study activity will be designed in a later round.');
  }
  function closeStub() { stub.value = null; }
  function beforeUnload(event: BeforeUnloadEvent) {
    if (guard.editor.value?.dirty()) { event.preventDefault(); event.returnValue = ''; }
  }
  onMounted(() => window.addEventListener('beforeunload', beforeUnload));
  onBeforeUnmount(() => { clearTimeout(toastTimer); window.removeEventListener('beforeunload', beforeUnload); });
  rememberPosition();
  return { book, sampleBook, nodes, sections, selectedId, selectedNode, mode, sideMode, notes, allNotes, showingAllNotes,
    graph, graphStatus, graphError, similarResults, similarStatus, similarError, discoveryKind, originBookId, activeImage, canBack, canContinue,
    guard, actionBusy, toast, stub, run, select, continueReading, backObject, action, closeSide, saveNote, deleteNote, openResult,
    returnOrigin, moveExercise, markDone, openImage, notesPage, returnFromNotes, comingSoon, closeStub };
}
