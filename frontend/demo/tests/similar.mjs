import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../src/", import.meta.url);
const serviceSource = await readFile(new URL("services/studyApi.js", root), "utf8");
const isolatedSource = serviceSource.replace(/^import .*;\r?\n/gm, "");
const harness = `
export class DemoApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
async function demoFetch(path, options) { return globalThis.__similarTestFetch(path, options); }
function normalizeGraph(payload) { return payload; }
${isolatedSource}
`;
const api = await import(`data:text/javascript;base64,${Buffer.from(harness).toString("base64")}`);

let requestedPath = "";
globalThis.__similarTestFetch = async path => {
  requestedPath = path;
  return {
    results: [
      { knowledge_id: 7, similarity_score: 1, label: "selected" },
      { knowledge_id: 8, similarity_score: "0.41", label: "lower duplicate" },
      { knowledge_id: 9, similarity_score: 0.91, label: "nearest" },
      { knowledge_id: 8, similarity_score: 0.82, label: "higher duplicate" },
      { knowledge_id: 10, similarity_score: "not-a-number", label: "invalid" },
      ...Array.from({ length: 12 }, (_, index) => ({
        knowledge_id: 20 + index,
        similarity_score: 0.8 - index / 100,
        label: `candidate ${index}`
      }))
    ]
  };
};

const response = await api.fetchSimilarKnowledge(7, { k: 10 });
assert.equal(requestedPath, "/api/demo/knowledge/7/similar?k=10&scope=book");
assert.equal(response.results.length, 10, "the UI adapter must return at most ten results");
assert.ok(response.results.every(result => result.knowledge_id !== 7), "the selected item must be excluded");
assert.equal(response.results.filter(result => result.knowledge_id === 8).length, 1, "duplicate items must collapse");
assert.equal(response.results.find(result => result.knowledge_id === 8).label, "higher duplicate");
assert.deepEqual(
  response.results.map(result => result.similarity_score),
  [...response.results.map(result => result.similarity_score)].sort((left, right) => right - left),
  "results must be sorted by numeric similarity"
);

const expandedResponse = await api.fetchSimilarKnowledge(7, { k: 200 });
assert.equal(requestedPath, "/api/demo/knowledge/7/similar?k=25&scope=book", "the service contract maximum is 25");
assert.ok(expandedResponse.results.length > 10, "the adapter may return more than the UI default when a caller requests it");
assert.ok(expandedResponse.results.length <= 25, "the service contract returns at most 25 results");
assert.equal(api.isUnavailable(new api.DemoApiError("missing", 404)), true);
assert.equal(api.isUnavailable(new api.DemoApiError("not implemented", 501)), true);
assert.equal(api.isUnavailable(new api.DemoApiError("temporarily unavailable", 503)), true);
assert.equal(api.isUnavailable(new api.DemoApiError("failed", 500)), false);

const appSource = await readFile(new URL("App.vue", root), "utf8");
const studySource = await readFile(new URL("components/StudyView.vue", root), "utf8");
const panelSource = await readFile(new URL("components/SearchPanel.vue", root), "utf8");
const i18nSource = await readFile(new URL("i18n.js", root), "utf8");
assert.doesNotMatch(`${appSource}\n${studySource}`, /crystalli[sz]/i, "Crystallize must not remain interactive");
assert.match(studySource, /\{\{ t\.cluster \}\}/, "the action label must be Cluster");
assert.match(panelSource, /<h2[^>]*>\{\{ t\.cluster \}\}<\/h2>/, "the panel heading must be Cluster");
assert.match(i18nSource, /cluster: "Cluster"/, "Cluster must be the exact user-facing label");
assert.doesNotMatch(`${studySource}\n${panelSource}\n${i18nSource}`, /Find similar/, "the overridden label must be absent");
assert.match(appSource, /fetchSimilarKnowledge\(sourceId, \{ k: 10 \}\)/);
assert.match(appSource, /createProjectionStore\(\)/);
assert.doesNotMatch(appSource, /fetchGraphSlice/);
assert.match(appSource, /const studyCache = new Map\(\)/);
for (const state of ["idle", "loading", "results", "empty", "unavailable", "error"]) {
  assert.match(panelSource, new RegExp(`status === '${state}'`), `Similar panel must render ${state}`);
}

delete globalThis.__similarTestFetch;
console.log("similar interaction contract: ok");
