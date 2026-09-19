import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'vite';
import { createRenderer, h, provide, shallowRef } from 'vue';

const original = { fetch: globalThis.fetch, location: globalThis.location };
const calls = [];
globalThis.location = { port: '', search: '', pathname: '/demo/' };
globalThis.fetch = async url => {
  calls.push(String(url));
  assert.equal(String(url), '/api/demo/notes', 'global Notes must not require a visible book request');
  return new Response(JSON.stringify({ notes: [{
    demo_note_id: 17, grimoire_id: 9, knowledge_id: 33, note_type: 'attached',
    tag: 'Retained', content: 'Writing retained after the only book was hidden',
    knowledge_label: null, book_title: null, source_available: false,
  }] }), { headers: { 'Content-Type': 'application/json' } });
};

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
try {
  const [{ demoFetch }, { useNoteEditor }, globalNotes, sanctuary] = await Promise.all([
    server.ssrLoadModule('/src/api.js'),
    import('../src/composables/useNoteEditor.js'),
    readFile('src/sanctuary/GlobalNotes.vue', 'utf8'),
    readFile('src/sanctuary/SanctuaryApp.vue', 'utf8'),
  ]);
  const data = await demoFetch('/api/demo/notes');
  assert.deepEqual(calls, ['/api/demo/notes']);
  assert.equal(data.notes[0].source_available, false);
  assert.equal(data.notes[0].content, 'Writing retained after the only book was hidden');
  assert(globalNotes.includes("demoFetch('/api/demo/notes')"));
  assert(globalNotes.includes('<NotesDesk v-else :t="t" :notes="notes" />'));
  assert(globalNotes.includes('await refreshNotes()'));
  assert(!globalNotes.includes('loading.value = true'));
  assert(sanctuary.includes('<GlobalNotes v-if="globalNotesOpen"'));
  assert(!sanctuary.match(/chosenBook[^\n]*<GlobalNotes/));

  const saved = [];
  const guard = { editor: shallowRef(null), run: async action => action() };
  const renderer = createRenderer({
    createElement: type => ({ type }), createText: text => ({ text }), createComment: text => ({ text }),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null,
  });
  let editor;
  const EditorHarness = { setup() {
    editor = useNoteEditor();
    return () => h('div');
  } };
  const app = renderer.createApp({ setup() {
    provide('noteGuard', guard);
    provide('apiError', error => { throw error; });
    provide('saveNote', async note => { saved.push({ ...note }); return { note: { demo_note_id: 17 } }; });
    return () => h(EditorHarness);
  } });
  app.mount({});
  editor.load(data.notes[0]);
  editor.content.value = 'First retained edit';
  await editor.save();
  editor.content.value = 'Second retained edit';
  await editor.save();
  assert.deepEqual(saved.map(note => [note.id, note.content]), [[17, 'First retained edit'], [17, 'Second retained edit']]);
  assert.equal(editor.selected.value.demo_note_id, 17);
  app.unmount();
  console.log('Global Notes: hidden-only-book wiring reaches retained writing without a visible grimoire request.');
} finally {
  await server.close();
  Object.assign(globalThis, original);
}
