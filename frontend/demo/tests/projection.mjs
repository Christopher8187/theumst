import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../src/", import.meta.url);
const serviceSource = await readFile(new URL("services/studyApi.js", root), "utf8");
const isolatedSource = serviceSource.replace(/^import .*;\r?\n/gm, "");
const harness = `
export class DemoApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
async function demoFetch(path, options) { return globalThis.__projectionTestFetch(path, options); }
${isolatedSource}
`;
const api = await import(`data:text/javascript;base64,${Buffer.from(harness).toString("base64")}`);

const revision = "projection-r17";
function chunk(chunkIndex, projectionRevision = revision) {
  const start = chunkIndex * 2;
  return {
    projection_revision: projectionRevision,
    chunk_index: chunkIndex,
    start_index: start,
    end_index: start + 2,
    nodes: [
      { knowledge_id: start + 1, label: `Idea ${start + 1}` },
      { knowledge_id: start + 2, label: `Idea ${start + 2}` }
    ],
    edges: [{
      source_knowledge_id: start + 1,
      target_knowledge_id: start + 2,
      relation_type: "supports"
    }]
  };
}

const manifest = {
  projection_revision: revision,
  book_revision: "book-r9",
  total_nodes: 6,
  chunk_size: 2,
  canvas_width: 1440,
  row_height: 72,
  side_lane_spacing: 188,
  positions: Array.from({ length: 6 }, (_, index) => ({
    knowledge_id: index + 1,
    index,
    type: index % 2 ? "context" : "theorem",
    graph_role: index % 2 ? "support" : "backbone",
    anchor_knowledge_id: index % 2 ? index : null,
    anchor_index: index % 2 ? index - 1 : null,
    fan_index: index % 2 ? 0 : null,
    lane: index % 2 ? 1 : 0
  })),
  initial_chunk: chunk(0)
};

const requestedPaths = [];
globalThis.__projectionTestFetch = async path => {
  requestedPaths.push(path);
  return path.endsWith("/chunks/2") ? chunk(2) : manifest;
};
await api.fetchGraphProjectionManifest(42);
await api.fetchGraphProjectionChunk(42, 2, { projectionRevision: revision });
assert.deepEqual(requestedPaths, [
  "/api/demo/grimoires/42/graph/projection",
  "/api/demo/grimoires/42/graph/projection/chunks/2"
]);

let manifestCalls = 0;
const chunkCalls = [];
const store = api.createProjectionStore({
  fetchManifest: async () => {
    manifestCalls += 1;
    return manifest;
  },
  fetchChunk: async (_bookId, chunkIndex) => {
    chunkCalls.push(chunkIndex);
    return chunk(chunkIndex);
  }
});

const initial = await store.load(42);
const initialMap = initial.chunks;
const initialEdge = initial.chunks.get(0).edges[0];
assert.equal(Object.isFrozen(initial), true, "projection snapshots must be shallow immutable");
assert.equal(initial.projection_revision, revision);
assert.equal(initial.canvas_width, 1440);
assert.equal(initial.row_height, 72);
assert.equal(initial.side_lane_spacing, 188);
assert.deepEqual(initial.positions[1], {
  knowledge_id: 2,
  index: 1,
  type: "context",
  graph_role: "support",
  anchor_knowledge_id: 1,
  anchor_index: 0,
  fan_index: 0,
  lane: 1
});
assert.equal(Object.isFrozen(initial.positions[1]), true, "server-authored positions must remain immutable");

const selectedOne = await store.ensureSelection(42, 1, revision);
assert.strictEqual(selectedOne.chunks, initialMap, "a loaded selection must preserve the chunk Map identity");
assert.strictEqual(selectedOne.chunks.get(0).edges[0], initialEdge);

const selectedThree = await store.ensureSelection(42, 3, revision);
const middleEdge = selectedThree.chunks.get(1).edges[0];
assert.equal(selectedThree.projection_revision, revision);
assert.notStrictEqual(selectedThree.chunks, initialMap, "inserting a chunk must replace the Map for Vue reactivity");
assert.strictEqual(selectedThree.chunks.get(0).edges[0], initialEdge, "existing edge identity must survive insertion");

const selectedFive = await store.ensureSelection(42, 5, revision);
const finalMap = selectedFive.chunks;
const finalEdge = selectedFive.chunks.get(2).edges[0];
assert.equal(selectedFive.projection_revision, revision);
assert.strictEqual(selectedFive.chunks.get(0).edges[0], initialEdge);
assert.strictEqual(selectedFive.chunks.get(1).edges[0], middleEdge);
assert.strictEqual(selectedFive.chunks.get(2).edges[0], finalEdge);

const selectedThreeAgain = await store.ensureSelection(42, 3, revision);
assert.strictEqual(selectedThreeAgain.chunks, finalMap, "a previously fetched fixed chunk must not be inserted twice");
assert.strictEqual(selectedThreeAgain.chunks.get(0).edges[0], initialEdge);
assert.strictEqual(selectedThreeAgain.chunks.get(1).edges[0], middleEdge);
assert.strictEqual(selectedThreeAgain.chunks.get(2).edges[0], finalEdge);
assert.equal(manifestCalls, 1, "three selections must reuse one manifest");
assert.deepEqual(chunkCalls, [1, 2], "each missing fixed chunk must be fetched exactly once");

const mismatchedStore = api.createProjectionStore({
  fetchManifest: async () => manifest,
  fetchChunk: async (_bookId, chunkIndex) => chunk(chunkIndex, "projection-r18")
});
await mismatchedStore.load(42);
await assert.rejects(
  mismatchedStore.ensureSelection(42, 3, revision),
  error => error?.name === "ProjectionContractError" && /changed/.test(error.message),
  "a chunk from another revision must be rejected"
);

const appSource = await readFile(new URL("App.vue", root), "utf8");
const studySource = await readFile(new URL("components/StudyView.vue", root), "utf8");
assert.doesNotMatch(`${serviceSource}\n${appSource}`, /\/graph\?focus|fetchGraphSlice|loadFocusedGraph/);
assert.match(appSource, /loadProjectionForSelection\(selectedBook\.value\.grimoire_id, id\)/);
assert.match(studySource, /:projection="projection"/);
assert.match(studySource, /@request-chunk="\$emit\('request-chunk', \$event\)"/);
assert.match(studySource, /@retry="\$emit\('retry'\)"/);

delete globalThis.__projectionTestFetch;
console.log("immutable projection adapter: ok");
