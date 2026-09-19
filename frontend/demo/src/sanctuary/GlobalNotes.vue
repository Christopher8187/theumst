<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, shallowRef } from 'vue';
import { demoFetch } from '../api';
import { useNoteGuard } from '../composables/useNoteGuard';
import NoteDecision from '../components/NoteDecision.vue';
import NotesDesk from '../components/NotesDesk.vue';
import FolioNavigation from './FolioNavigation.vue';
import LanguageControl from './LanguageControl.vue';
import RealmFolio from './RealmFolio.vue';
import { useWisdomI18n } from './i18n';

const emit = defineEmits<{ close: [] }>();
const panel = shallowRef<HTMLElement | null>(null);
const { t } = useWisdomI18n();
const notes = ref<Record<string, unknown>[]>([]);
const initialLoading = shallowRef(true);
const initialError = shallowRef('');
const toast = shallowRef('');
let toastTimer: ReturnType<typeof setTimeout> | undefined;

function notify(message: string) {
  toast.value = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.value = '', 2600);
}
function apiError(reason: unknown) {
  notify(reason instanceof Error ? reason.message : t.value.actionFailed);
}

const guard = useNoteGuard(apiError);
const busy = computed(() => initialLoading.value || guard.running.value || guard.saving.value || !!guard.editor.value?.saving());

async function loadInitialNotes() {
  initialLoading.value = true;
  initialError.value = '';
  try {
    const data = await demoFetch('/api/demo/notes');
    notes.value = data.notes || [];
  } catch (reason) {
    initialError.value = reason instanceof Error ? reason.message : t.value.actionFailed;
  } finally {
    initialLoading.value = false;
  }
}
async function refreshNotes() {
  try {
    const data = await demoFetch('/api/demo/notes');
    notes.value = data.notes || [];
  } catch (reason) {
    apiError(reason);
  }
}
async function saveNote(note: Record<string, unknown>) {
  const noteId = note.id || note.demo_note_id;
  const result = await demoFetch(noteId ? `/api/demo/notes/${noteId}` : '/api/demo/notes', {
    method: noteId ? 'PUT' : 'POST',
    body: JSON.stringify({
      grimoire_id: note.grimoire_id ?? null,
      knowledge_id: note.knowledge_id ?? null,
      note_type: note.note_type,
      tag: note.tag,
      content: note.content,
    }),
  });
  await refreshNotes();
  notify(t.value.saved);
  return result;
}
async function deleteNote(note: Record<string, unknown>) {
  await demoFetch(`/api/demo/notes/${note.demo_note_id}`, { method: 'DELETE' });
  await refreshNotes();
}
function close() {
  guard.run(() => emit('close'));
}
function keydown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || guard.pending.value) return;
  event.preventDefault();
  close();
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (!guard.editor.value?.dirty()) return;
  event.preventDefault();
  event.returnValue = '';
}

provide('noteGuard', guard);
provide('saveNote', saveNote);
provide('deleteNote', deleteNote);
provide('apiError', apiError);

onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload);
  await loadInitialNotes();
  await nextTick();
  panel.value?.querySelector<HTMLButtonElement>('header button')?.focus({ preventScroll: true });
});
onBeforeUnmount(() => {
  clearTimeout(toastTimer);
  window.removeEventListener('beforeunload', beforeUnload);
});
</script>

<template>
  <section ref="panel" class="global-notes" :aria-label="t.notes" @keydown.esc.capture="keydown">
    <RealmFolio class="global-notes-folio" stacked :inert="busy || !!guard.pending.value">
      <header class="global-notes-header">
        <FolioNavigation :title="t.notes" :back-label="t.backToTree" :disabled="busy" @back="close" />
        <LanguageControl />
      </header>
      <div v-if="initialLoading" class="global-notes-state" role="status">{{ t.loadingLibrary }}</div>
      <div v-else-if="initialError" class="global-notes-state" role="alert">
        <p>{{ initialError }}</p>
        <button type="button" @click="loadInitialNotes">{{ t.retry }}</button>
      </div>
      <NotesDesk v-else :t="t" :notes="notes" />
    </RealmFolio>
    <p v-if="toast" class="global-notes-toast" role="status">{{ toast }}</p>
    <NoteDecision :t="t" :guard="guard" />
  </section>
</template>

<style scoped>
.global-notes{position:fixed;inset:0;z-index:70;padding:64px max(2.7%,calc((100vw - 1500px)/2)) 3.5%;background:#10263bbd;backdrop-filter:blur(13px);color:#e2ebee;font:13px/1.5 'Bahnschrift','Segoe UI',sans-serif;--text-line:#b9d9dd33}
.global-notes-folio{height:100%;display:grid;grid-template-rows:66px minmax(0,1fr)}
.global-notes-header{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:12px 28px;border-bottom:1px solid var(--text-line)}
.global-notes-state{display:grid;place-content:center;justify-items:center;gap:12px;color:#c6d9df}
.global-notes-state p{margin:0}
.global-notes-state button{min-height:40px;padding:8px 16px;border:1px solid #a4cbd84d;background:#15364465;color:#d7e9e7;border-radius:2px}
.global-notes-toast{position:fixed;right:4%;bottom:24px;margin:0;padding:11px 17px;border:1px solid #b9d9dd55;background:#173448f5;color:#dce9e8}
.global-notes-folio :deep(*){box-sizing:border-box;scrollbar-width:thin;scrollbar-color:#a7c5d16b transparent}
.global-notes-folio :deep(button),.global-notes-folio :deep(input),.global-notes-folio :deep(textarea){font:inherit}
.global-notes-folio :deep(button){cursor:pointer}
.global-notes-folio :deep(button:focus-visible),.global-notes-folio :deep(input:focus-visible),.global-notes-folio :deep(textarea:focus-visible){outline:2px solid #bee9e4;outline-offset:3px}
.global-notes-folio :deep(.notes-desk){display:grid;grid-template-columns:1.05fr .95fr;height:100%;min-height:0}
.global-notes-folio :deep(.note-editor-pane),.global-notes-folio :deep(.note-constellation-pane){display:flex;flex-direction:column;min-width:0;min-height:0;padding:25px 28px}
.global-notes-folio :deep(.notes-desk header){display:flex;justify-content:space-between;gap:16px;align-items:flex-start;min-width:0}
.global-notes-folio :deep(.notes-desk h1),.global-notes-folio :deep(.notes-desk h2){font:italic 20px Georgia,serif;color:#d7e5e6;margin:5px 0}
.global-notes-folio :deep(.notes-desk label){display:flex;flex-direction:column;gap:6px;margin:10px 0;color:#b7c9d3;font-size:11px}
.global-notes-folio :deep(.notes-desk input){min-height:36px;padding:9px;color:#e2e8e9;background:#132e4080;border:1px solid #aecfd23a;border-radius:2px}
.global-notes-folio :deep(.notes-desk textarea){min-height:100px;flex:1;resize:none;padding:14px 15px;color:#e6eae5;border:1px solid #a8cad23f;border-radius:2px;background:repeating-linear-gradient(transparent 0 29px,#bed7de0f 29px 30px),#142e3d54;font:15px/30px Georgia,serif}
.global-notes-folio :deep(.notes-help){font-size:12px;color:#b6c8d1}
.global-notes-folio :deep(.note-groups){overflow:auto;min-height:0}
.global-notes-folio :deep(.note-groups h3){font:11px 'Courier New',monospace;color:#c8d8dc}
.global-notes-folio :deep(.note-groups section>button){display:flex;flex-direction:column;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--text-line);padding:12px 6px;color:#cfdee3}
.global-notes-folio :deep(.note-groups section>button.active){background:#a3d4d916}
.global-notes-folio :deep(.note-groups strong){font:14px Georgia,serif;color:#e0e6e4}
.global-notes-folio :deep(.note-groups p){font-size:12px;color:#b8cbd3;white-space:pre-wrap;overflow-wrap:anywhere}
.global-notes-folio :deep(.note-groups small){font:10px 'Courier New',monospace;color:#bdb2c8}
.global-notes-folio :deep(.note-editor-actions){display:flex;gap:12px;justify-content:space-between;padding-top:15px}
.global-notes-folio :deep(.note-editor-actions button),.global-notes-folio :deep(.note-constellation-pane header button){min-height:35px;padding:8px 12px;border:1px solid #a4cbd84d;background:#15364465;color:#d7e9e7;border-radius:2px}
.global-notes-folio :deep(.demo-kicker){margin:0 0 4px;font:9px 'Courier New',monospace;color:#a7baca}
@media(max-width:900px){.global-notes{overflow:auto;padding:18px 16px 28px}.global-notes-folio{height:auto;min-height:calc(100dvh - 46px);grid-template-rows:auto minmax(0,1fr)}.global-notes-header{padding:13px 21px}.global-notes-folio :deep(.notes-desk){grid-template-columns:1fr}.global-notes-folio :deep(.note-editor-pane){min-height:550px}.global-notes-folio :deep(.note-constellation-pane){min-height:360px;max-height:650px;border-top:1px solid var(--text-line)}}
@media(max-width:540px){.global-notes{padding-inline:8px}.global-notes-header{padding-inline:13px}.global-notes-folio :deep(.note-editor-pane),.global-notes-folio :deep(.note-constellation-pane){padding:20px 16px}}
</style>
