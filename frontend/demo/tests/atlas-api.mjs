import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { normalizeGraph } from "../src/domain/graph.js";
import { buildAtlas } from "../src/domain/atlas.js";

const source = await readFile(new URL("../src/services/studyApi.js", import.meta.url), "utf8");
const adapter = source.replace(/^import .*;\r?\n/gm, "");
globalThis.__atlasNormalize = normalizeGraph;
globalThis.__atlasFetch = async path => {
  const query = new URL(path, "https://example.invalid").searchParams;
  assert.equal(query.get("view"), "atlas", "the reader must request authored Atlas input");
  assert.equal(query.get("focus"), "13");
  return {
    authored_dependencies: true,
    focus_knowledge_id: 13,
    nodes: Array.from({ length: 36 }, (_, i) => ({ knowledge_id: i + 1, label: `Item ${i+1}` })),
    edges: [[4,13],[12,13],[13,14]].map(([a,b]) => ({ source_knowledge_id:a, target_knowledge_id:b, relation_type:"dependency" })),
  };
};
const harness = `const demoFetch=globalThis.__atlasFetch; const normalizeGraph=globalThis.__atlasNormalize; ${adapter}`;
const { fetchGraphSlice } = await import(`data:text/javascript;base64,${Buffer.from(harness).toString("base64")}`);
const graph = await fetchGraphSlice(1, 13);
assert.equal(graph.authored_dependencies, true);
for (const view of ["reading", "hierarchy"]) {
  const layout = buildAtlas(graph.nodes, [], graph.edges, 13, {book:3, dependency:2, view});
  assert(layout.edges.some(e => e.type === "dependency" && e.a === 4 && e.b === 13));
  const dependency = layout.edges.find(e => e.type === "dependency" && e.a === 12 && e.b === 13);
  const order = layout.edges.find(e => e.type === "order" && e.a === 12 && e.b === 13);
  assert(dependency && order, "coincident reading-order and dependency arrows both remain");
  assert.notDeepEqual(dependency.points, order.points);
}
delete globalThis.__atlasFetch;
delete globalThis.__atlasNormalize;
console.log("Atlas API selection, normalization and both arrow layouts: passed");
