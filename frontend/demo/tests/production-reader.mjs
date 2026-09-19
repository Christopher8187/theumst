import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createRenderer, h, nextTick, ref, watch } from 'vue';

// Simulated HTTP checks exercise the production composable, not the prototype adapter.
const original = { fetch: globalThis.fetch, window: globalThis.window, document: globalThis.document, location: globalThis.location };
globalThis.location = { port: '', search: '' };
globalThis.window = { location: globalThis.location, addEventListener() {}, removeEventListener() {} };
globalThis.document = { activeElement: null };
const rows = [
  { knowledge_id: 101, type: 'context', completed: true },
  { knowledge_id: 504, type: 'exercise', completed: false },
  { knowledge_id: 208, type: 'definition', completed: false },
  { knowledge_id: 901, type: 'exercise', completed: false },
  { knowledge_id: 306, type: 'theorem', completed: false },
].map(row => ({ ...row, section_id: 7, label: `Object ${row.knowledge_id}`, breadcrumbs: [] }));
const positions = { current_knowledge_id: 101, questions_knowledge_id: 504 };
const calls = [];
globalThis.fetch = async (url, options = {}) => {
  calls.push([url, options]);
  let data;
  if (url.endsWith('/knowledge')) data = { book: { grimoire_id: 88, title: 'Persisted book' }, knowledge: structuredClone(rows), sections: [], ...positions };
  else if (url.includes('/graph?')) data = { nodes: rows, edges: [], authored_dependencies: true };
  else if (/\/knowledge\/\d+$/.test(url)) data = { knowledge: { ...rows.find(row => row.knowledge_id === Number(url.split('/').at(-1))), statement: 'Real detail', working: '' } };
  else if (url.endsWith('/state')) { const body = JSON.parse(options.body); positions[body.realm === 'questions' ? 'questions_knowledge_id' : 'current_knowledge_id'] = body.knowledge_id; data = {}; }
  else if (url.includes('/progress/')) { const row = rows.find(row => row.knowledge_id === Number(url.split('/').at(-1))); row.completed = JSON.parse(options.body).completed; data = { progress: { completed: row.completed } }; }
  else if (url.endsWith('/dependencies')) data = { results: [{ knowledge_id: 101, grimoire_id: 88, label: 'Prerequisite' }] };
  else throw Error(`Unexpected request ${url}`);
  return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
};
const renderer = createRenderer({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null });
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
let app;
try {
  const { useTextStudy } = await server.ssrLoadModule('/src/sanctuary/text/useTextStudy.ts');
  let state;
  const entranceMode = ref('text'), completed = [];
  function mount() {
    app = renderer.createApp({ setup() {
      state = useTextStudy('88', {savedPositionUnavailable:'Saved position unavailable'}, (id, count) => completed.push([id, count]), entranceMode);
      watch(state.mode, value => { entranceMode.value = value; });
      return () => h('div');
    } }); app.mount({});
  }
  async function ready() { for (let n = 0; n < 100 && state.loading.value; n++) await new Promise(resolve => setTimeout(resolve, 2)); assert.equal(state.error.value, ''); assert.equal(state.loading.value, false); }
  async function act(fn, ...args) { await state.run(fn, ...args); await nextTick(); }
  mount(); await ready();
  assert.equal(state.selectedId.value, 101);
  await act(state.continueReading); assert.equal(state.selectedId.value, 208);
  await act(state.backObject); assert.equal(state.selectedId.value, 101);
  await act(state.select, 901); assert.equal(state.mode.value, 'questions');
  await act(state.backObject); assert.equal(state.selectedId.value, 504);
  await act(state.continueReading); assert.equal(state.selectedId.value, 901);
  await act(state.select, 208); assert.equal(state.mode.value, 'text');
  await act(state.action, 'dependencies'); assert.equal(state.similarResults.value[0].knowledge_id, 101);
  await act(state.markDone, state.selectedNode.value); assert.deepEqual(completed.at(-1), ['88', 2]);
  let dirty = true;
  state.guard.editor.value = { dirty: () => dirty, saving: () => false, discard: () => { dirty = false; } };
  await act(state.continueReading); assert.equal(state.selectedId.value, 208); assert(state.guard.pending.value);
  await state.guard.proceed(false); await nextTick(); assert.equal(state.selectedId.value, 306);
  assert.equal(state.canContinue.value, false);
  app.unmount(); mount(); await ready();
  assert.equal(state.selectedId.value, 306);
  assert.equal(state.nodes.value.find(row => row.knowledge_id === 208).completed, true);
  assert(calls.some(([url, options]) => url.endsWith('/state') && options.method === 'PUT'));
  app.unmount(); positions.current_knowledge_id = 999999; mount(); await ready();
  assert.equal(state.selectedId.value, 101);
  assert.equal(state.toast.value, 'Saved position unavailable');
  assert.equal(positions.current_knowledge_id, 999999, 'Fallback must not overwrite saved position');
  app.unmount(); rows.splice(0, rows.length, {knowledge_id: 42, type: 'exercise', completed: false});
  mount(); await ready(); assert.equal(state.selectedId.value, undefined); assert.equal(state.selectedNode.value, null);
  assert.equal(state.canContinue.value, false); assert.equal(state.canBack.value, false);
  app.unmount(); rows.splice(0, rows.length, {knowledge_id: 43, type: 'definition', completed: false});
  entranceMode.value = 'questions'; mount(); await ready(); assert.equal(state.selectedId.value, undefined); assert.equal(state.selectedNode.value, null);
  const { readFile } = await import('node:fs/promises');
  const copy = await readFile('src/sanctuary/i18n.ts', 'utf8');
  assert(copy.includes("cluster:'查找邻近知识'")); assert(copy.includes("cluster:'近い知識を探す'"));
  console.log('Production reader: realm navigation, parent feedback, HTTP writes, reload, dependencies and draft guard passed.');
} finally { app?.unmount(); await server.close(); Object.assign(globalThis, original); }
