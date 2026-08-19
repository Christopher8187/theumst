import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

async function importSource(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

const {
  buildContentsTree,
  contentsItemKey,
  defaultExpandedContents,
  findSectionPath,
  flattenVisibleContents
} = await importSource("../src/domain/contents.js");
const {
  canonicalKnowledgeType,
  hasProjectionChunk,
  isBookOrderProjection,
  isProjectionBackboneType,
  mergeProjectionChunks,
  normalizeProjectionManifest,
  projectionChunkAtScroll,
  projectionChunkIndexForKnowledge,
  projectionChunkWindow,
  projectionPosition,
  projectionScrollTopForKnowledge,
  safeGraphRole
} = await importSource("../src/domain/graph.js");

const sections = [
  { section_id: 10, parent_section: null, section_number: "1", section_name: "Groups" },
  { section_id: 11, parent_section: 10, section_number: "1.1", section_name: "Operations" },
  { section_id: 12, parent_section: 11, section_number: "1.1.1", section_name: "Associativity" },
  { section_id: 20, parent_section: null, section_number: "2", section_name: "Rings" },
  { section_id: 21, parent_section: 999, section_number: "2.1", section_name: "Honest orphan" }
];
const tree = buildContentsTree(sections);
assert.deepEqual(tree.map(item => item.section_id), [10, 20, 21], "only supplied parent metadata creates nesting");
assert.deepEqual(tree[0].children.map(item => item.section_id), [11]);
assert.deepEqual(tree[0].children[0].children.map(item => item.section_id), [12]);
assert.deepEqual(findSectionPath(tree, 12).map(item => item.section_id), [10, 11, 12]);

const expandedForCurrent = defaultExpandedContents(tree, 12);
assert(expandedForCurrent.has(contentsItemKey(tree[0])));
assert(expandedForCurrent.has(contentsItemKey(tree[0].children[0])));
assert.deepEqual(flattenVisibleContents(tree, expandedForCurrent).map(row => row.item.section_id), [10, 11, 12, 20, 21]);
assert.deepEqual(flattenVisibleContents(tree, new Set()).map(row => row.item.section_id), [10, 20, 21]);

const cycleTree = buildContentsTree([
  { section_id: 1, parent_section: 2, section_number: "A" },
  { section_id: 2, parent_section: 1, section_number: "B" }
]);
assert.equal(cycleTree.length, 2, "cyclic metadata stays visible without an invented hierarchy");

assert.equal(canonicalKnowledgeType("  Definition  "), "definition");
for (const type of ["definition", " THEOREM ", "Notation"]) {
  assert.equal(isProjectionBackboneType(type), true, `${type} is an exact canonical backbone type`);
}
for (const type of ["definition-extra", "proposition", "exercise", "JAS", "example", ""]) {
  assert.equal(isProjectionBackboneType(type), false, `${type || "empty"} stays off the backbone`);
}
assert.equal(safeGraphRole({ type: "exercise", graph_role: "backbone" }), "assessment");
assert.equal(safeGraphRole({ type: "just a statement", graph_role: "backbone" }), "fragment");
assert.equal(safeGraphRole({ type: "just-a-statement", graph_role: "backbone" }), "fragment");
assert.equal(safeGraphRole({ type: "definition-extra", graph_role: "backbone" }), "support");

const manifestPayload = {
  projection_revision: "projection-r7",
  book_revision: "book-r3",
  total_nodes: 350,
  chunk_size: 100,
  initial_chunk: 1,
  positions: new Map([
    [90, { knowledge_id: 90, index: 0, type: "remark", anchor_knowledge_id: null }],
    [101, { knowledge_id: 101, index: 100, type: " definition " }],
    [102, { knowledge_id: 102, index: 101, type: "example", anchor_knowledge_id: 101, fan_index: 0 }],
    [103, { knowledge_id: 103, index: 102, type: "exercise", anchor_knowledge_id: 101, fan_index: 1 }],
    [104, { knowledge_id: 104, index: 103, type: "THEOREM", anchor_knowledge_id: 101 }],
    [105, { knowledge_id: 105, index: 104, type: "JAS", anchor_knowledge_id: 104, fan_index: 0 }],
    [201, { knowledge_id: 201, index: 200, type: "notation" }],
    [301, { knowledge_id: 301, index: 300, type: "theorem" }]
  ])
};

const projection = {
  ...manifestPayload,
  chunks: new Map([
    [0, {
      chunk_index: 0,
      nodes: [{ knowledge_id: 90, label: "Leading prefix", type: "remark" }],
      edges: [{ edge_id: "forbidden-prefix", source_knowledge_id: 90, target_knowledge_id: 101, relation_type: "book_order_v1" }]
    }],
    [1, {
      chunk_index: 1,
      nodes: [
        { knowledge_id: 101, label: "A", type: " definition " },
        { knowledge_id: 102, label: "B", type: "example" },
        { knowledge_id: 103, label: "C", type: "exercise", graph_role: "backbone" },
        { knowledge_id: 104, label: "D", type: "THEOREM" },
        { knowledge_id: 105, label: "E", type: "JAS", graph_role: "backbone" }
      ],
      edges: [
        { edge_id: "edge-a-b", source_knowledge_id: 101, target_knowledge_id: 102, relation_type: "book_order_v1" },
        { edge_id: "edge-a-c", source_knowledge_id: 101, target_knowledge_id: 103, relation_type: "book-order-v1" },
        { edge_id: "edge-a-d", source_knowledge_id: 101, target_knowledge_id: 104, relation_type: "book order v1" },
        { edge_id: "edge-d-e", source_knowledge_id: 104, target_knowledge_id: 105, relation_type: "book_order_v1" },
        { source_knowledge_id: 101, target_knowledge_id: 105, relation_type: "book_order_v1" },
        { edge_id: "not-projection", source_knowledge_id: 101, target_knowledge_id: 105, relation_type: "similarity" }
      ]
    }],
    [2, { chunk_index: 2, nodes: [{ knowledge_id: 201, label: "Middle notation", type: "notation" }], edges: [] }],
    [3, { chunk_index: 3, nodes: [{ knowledge_id: 301, label: "Later theorem", type: "theorem" }], edges: [] }]
  ])
};

const manifest = normalizeProjectionManifest(manifestPayload);
assert.equal(manifest.projection_revision, "projection-r7");
assert.equal(manifest.book_revision, "book-r3");
assert.equal(manifest.chunk_count, 4);
assert.equal(manifest.positions.get(102).anchor_knowledge_id, 101, "the stored anchor is retained exactly");
assert.equal(manifest.positions.get(90).anchor_knowledge_id, null, "leading non-main stays unanchored");
assert.equal(
  normalizeProjectionManifest({ ...manifestPayload, manifest: { projection_revision: "wrong" } }).projection_revision,
  "projection-r7",
  "canonical top-level metadata takes precedence over the optional nested compatibility shape"
);
assert.equal(
  normalizeProjectionManifest({ manifest: manifestPayload }).projection_revision,
  "projection-r7",
  "the previous nested manifest shape remains a compatibility fallback"
);
assert.equal(hasProjectionChunk(projection, 0), true, "Map-backed chunks are consumed directly");
assert.equal(hasProjectionChunk(projection, 4), false);

const merged = mergeProjectionChunks(projection, [0, 1, 2]);
assert.deepEqual(
  merged.edges.map(edge => [edge.edge_id, edge.source_knowledge_id, edge.target_knowledge_id]),
  [
    ["edge-a-b", 101, 102],
    ["edge-a-c", 101, 103],
    ["edge-a-d", 101, 104],
    ["edge-d-e", 104, 105]
  ],
  "only stable server-supplied A→B, A→C, A→D, D→E projection edges survive"
);
assert(merged.edges.every(edge => isBookOrderProjection(edge.relation_type)));
assert(!merged.edges.some(edge => edge.source_knowledge_id === 90), "a leading side item can never become an anchor");
assert.equal(merged.nodes.find(node => node.knowledge_id === 103).graph_role, "assessment");
assert.equal(merged.nodes.find(node => node.knowledge_id === 105).graph_role, "fragment");

const positions = new Map(merged.nodes.map(node => [node.knowledge_id, node.position]));
assert.equal(positions.get(101).x, manifest.center_x);
assert.equal(positions.get(104).x, manifest.center_x, "exact backbone types share the central lane");
assert(positions.get(102).x < manifest.center_x);
assert(positions.get(103).x > manifest.center_x, "the A fan alternates across the central lane");
assert.notEqual(positions.get(103).x, manifest.center_x, "Exercise stays off the central backbone");
assert.notEqual(positions.get(105).x, manifest.center_x, "JAS stays off the central backbone");
for (const edge of merged.edges) {
  assert(
    positions.get(edge.target_knowledge_id).y < positions.get(edge.source_knowledge_id).y,
    `${edge.edge_id} points upward in the fixed projection`
  );
}
const cards = merged.nodes.filter(node => [101, 102, 103, 104, 105].includes(node.knowledge_id));
for (let leftIndex = 0; leftIndex < cards.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < cards.length; rightIndex += 1) {
    const left = cards[leftIndex].position;
    const right = cards[rightIndex].position;
    assert.equal(
      Math.abs(left.x - right.x) < 172 && Math.abs(left.y - right.y) < 68,
      false,
      `cards ${cards[leftIndex].knowledge_id} and ${cards[rightIndex].knowledge_id} do not overlap`
    );
  }
}

// Selection never changes the immutable projection revision or its stable edge IDs.
const threeSelections = [102, 103, 104].map(selectedId => ({
  selectedId,
  chunkIndex: projectionChunkIndexForKnowledge(manifest, selectedId),
  view: mergeProjectionChunks(projection, [0, 1, 2])
}));
assert.deepEqual(threeSelections.map(item => item.chunkIndex), [1, 1, 1]);
assert.deepEqual(threeSelections.map(item => item.view.projection_revision), ["projection-r7", "projection-r7", "projection-r7"]);
assert.deepEqual(
  threeSelections.map(item => item.view.edges.map(edge => edge.edge_id)),
  threeSelections.map(() => ["edge-a-b", "edge-a-c", "edge-a-d", "edge-d-e"])
);

assert.deepEqual(projectionChunkWindow(1, manifest), [0, 1, 2]);
assert.deepEqual(projectionChunkWindow(2, manifest), [1, 2, 3]);
assert.deepEqual(projectionChunkWindow(1, manifest), [0, 1, 2], "returning downward remounts the same adjacent chunks");
assert.equal(projectionChunkAtScroll(manifest, manifest.total_height - 700, 600), 0, "scrolling to the bottom reaches the first chunk");
assert.equal(projectionChunkAtScroll(manifest, 0, 600), 3, "scrolling to the top reaches the last chunk");

const scrollBefore = projectionScrollTopForKnowledge(manifest, 101, 680);
const partialProjection = { ...manifestPayload, chunks: new Map([[1, projection.chunks.get(1)]]) };
const scrollAfter = projectionScrollTopForKnowledge(
  normalizeProjectionManifest(partialProjection),
  101,
  680
);
assert.equal(scrollBefore, scrollAfter, "selected-item scroll geometry is independent of loaded chunks");
assert.equal(
  projectionPosition({ knowledge_id: 101, type: "definition" }, manifest).y,
  mergeProjectionChunks(partialProjection, [1]).nodes.find(node => node.knowledge_id === 101).position.y,
  "global coordinates stay fixed when adjacent chunks mount or unmount"
);
assert.equal(mergeProjectionChunks(partialProjection, [1]).manifest.total_height, manifest.total_height, "the full-height anchor spacer is stable");

// Production-shaped regression: 6,310 global indices with two side items per
// stored spine anchor must not accumulate ever-deeper lanes across the book.
const productionPositions = new Map(Array.from({ length: 6310 }, (_, index) => {
  const offset = index % 3;
  const knowledgeId = index + 1;
  const anchorIndex = index - offset;
  return [knowledgeId, {
    knowledge_id: knowledgeId,
    index,
    type: offset === 0 ? "definition" : (offset === 1 ? "example" : "JAS"),
    anchor_knowledge_id: offset === 0 ? null : anchorIndex + 1,
    fan_index: offset === 0 ? null : index,
    // A bad global lane value from an earlier client must not influence layout.
    lane: offset === 0 ? 0 : index
  }];
}));
const productionManifest = normalizeProjectionManifest({
  projection_revision: "production-shape-r1",
  book_revision: "production-book-r1",
  total_nodes: 6310,
  chunk_size: 100,
  initial_chunk: 0,
  positions: productionPositions
});
assert.equal(productionManifest.max_fan_depth, 1, "fan depth is measured per stored anchor");
assert.equal(productionManifest.width, 1000, "two-item fans keep the full 6,310-item canvas compact");
assert.deepEqual(
  [productionManifest.positions.get(2).lane, productionManifest.positions.get(3).lane],
  [-1, 1]
);
assert.deepEqual(
  [productionManifest.positions.get(6308).lane, productionManifest.positions.get(6309).lane],
  [-1, 1],
  "far-late fans reuse the same compact lanes instead of accumulating global depth"
);
assert.deepEqual(
  [productionManifest.positions.get(6308).fan_index, productionManifest.positions.get(6309).fan_index],
  [0, 1],
  "canonical fan_index is compacted independently for every stored anchor"
);
assert.equal(projectionPosition({ knowledge_id: 6307, type: "definition" }, productionManifest).x, 500);
assert.equal(projectionPosition({ knowledge_id: 6308, type: "example" }, productionManifest).x, 300);
assert.equal(projectionPosition({ knowledge_id: 6309, type: "JAS" }, productionManifest).x, 700);

const graphComponentSource = await readFile(new URL("../src/components/KnowledgeGraph.vue", import.meta.url), "utf8");
assert.match(graphComponentSource, /projection:\s*\{ type: Object/);
assert.match(graphComponentSource, /status:\s*\{ type: String/);
assert.match(graphComponentSource, /error:\s*\{ type: \[String, Error, Object\]/);
assert.match(graphComponentSource, /normalizeProjectionManifest\(props\.projection \|\| \{\}\)/, "top-level projection metadata is canonical");
assert.match(graphComponentSource, /if \(props\.status\) return props\.status;/, "StudyView loading status wins over projection fallback state");
assert.doesNotMatch(graphComponentSource, /\bgraph:\s*\{ type: Object/, "the component no longer accepts a focused graph slice");
assert.doesNotMatch(graphComponentSource, /boundedNeighborhood|compactBookOrderFans|graphLayout/, "the client does not derive projection topology");
assert.match(graphComponentSource, /emit\("request-chunk", index\)/);
assert.match(graphComponentSource, /if \(hasProjectionChunk\(props\.projection, index\)\) return;/, "loaded chunks never emit a request");
assert.match(graphComponentSource, /:key="edge\.edge_id"/, "stable server edge IDs key the rendered links");
assert.match(graphComponentSource, /projection-spacer[\s\S]*manifest\.total_height/, "virtualized nodes sit in a stable full-book spacer");
assert.match(graphComponentSource, /projectionChunkWindow\(activeChunkIndex\.value, manifest\.value, 1\)/, "current and adjacent chunks are mounted");
assert.match(graphComponentSource, /@scroll\.passive="onViewportScroll"/, "scrolling can load chunks in both directions");
assert.match(graphComponentSource, /await scrollToKnowledge\(selectedId\)/, "loaded selection scrolls and highlights without replacing the revision");

console.log("graph-contents: assertions passed");
