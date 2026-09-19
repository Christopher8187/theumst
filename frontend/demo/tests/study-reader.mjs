import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createRenderer, h, nextTick, ref, watch } from 'vue';

// Mount the actual reader, including its note guard and parent mode feedback.
// No browser DOM is needed for this state regression.
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
const previousWindow = globalThis.window;
globalThis.window = { location: { search: '' }, addEventListener() {}, removeEventListener() {} };
const renderer = createRenderer({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
  parentNode: () => null, nextSibling: () => null,
});
let app;
try {
  const { useTextStudy } = await server.ssrLoadModule('/prototypes/tree-of-wisdom/text/useTextStudy.ts');
  const entranceMode = ref('text');
  let state;
  app = renderer.createApp({ setup() {
    state = useTextStudy('analysis', {}, () => {}, entranceMode);
    watch(state.mode, value => { entranceMode.value = value; });
    return () => h('div');
  } });
  app.mount({});
  const act = async (operation, ...args) => { await state.run(operation, ...args); await nextTick(); };
  const position = (id, mode = 'text') => {
    assert.equal(state.selectedId.value, id);
    assert.equal(state.mode.value, mode);
    assert.equal(state.actionBusy.value, false);
  };

  position(1);
  assert.equal(state.canBack.value, false);
  await act(state.continueReading); position(2);
  await act(state.backObject); position(1);

  // A graph selection must not make Back jump through unrelated visit history.
  await act(state.select, 14); position(14);
  await act(state.backObject); position(13);
  await act(state.continueReading); position(14);
  await act(state.continueReading); position(18); // 15, 16 and 17 are exercises.
  await act(state.backObject); position(14);

  // Selecting a non-exercise from Questions keeps subsequent navigation in Text.
  await act(state.select, 15); position(15, 'questions');
  await act(state.select, 18); position(18);
  await act(state.backObject); position(14);
  await act(state.continueReading); position(18);

  // Walk both complete sequences, including completed objects and end boundaries.
  for (const mode of ['text', 'questions']) {
    const eligible = state.nodes.value.filter(node => (node.type === 'exercise') === (mode === 'questions'));
    eligible[1].completed = true;
    await act(state.select, eligible[0].knowledge_id);
    assert.equal(state.canBack.value, false);
    await act(state.backObject); position(eligible[0].knowledge_id, mode);
    for (const node of eligible.slice(1)) {
      assert.equal(state.canContinue.value, true);
      await act(state.continueReading); position(node.knowledge_id, mode);
    }
    assert.equal(state.canContinue.value, false);
    for (const node of eligible.slice(0, -1).reverse()) {
      assert.equal(state.canBack.value, true);
      await act(state.backObject); position(node.knowledge_id, mode);
    }
    assert.equal(state.canBack.value, false);
  }

  // Pending writing still defers navigation until the learner chooses.
  await act(state.select, 14);
  let dirty = true;
  state.guard.editor.value = { dirty: () => dirty, saving: () => false, discard: () => { dirty = false; } };
  await act(state.continueReading); position(14);
  assert(state.guard.pending.value);
  await state.guard.proceed(false); await nextTick(); position(18);
  console.log('Actual reader Back/Continue, graph jumps, realm feedback, boundaries and draft guard passed.');
} finally {
  app?.unmount();
  globalThis.window = previousWindow;
  await server.close();
}
