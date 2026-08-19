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
  MAX_GRAPH_NODES,
  MAX_RENDERED_GRAPH_NODES,
  boundedNeighborhood,
  graphCanvasHeightForRanks,
  graphCanvasWidthForSideLanes,
  graphLayout,
  inspectBookOrderProjection,
  isBookOrderProjection,
  normalizeGraph,
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

const normalized = normalizeGraph({
  focus_knowledge_id: 1,
  graph_revision: "fixture-1",
  nodes: [
    { knowledge_id: 1, label: "Definition", type: "definition", graph_role: "backbone" },
    { knowledge_id: 2, label: "Exercise", type: "exercise", graph_role: "backbone" },
    { knowledge_id: 3, label: "JAS", type: "JAS", graph_role: "backbone" },
    { knowledge_id: 4, label: "Support", type: "example", graph_role: "support" },
    { knowledge_id: 5, label: "Disconnected", type: "theorem", graph_role: "backbone" }
  ],
  edges: [
    { source_knowledge_id: 1, target_knowledge_id: 4, relation_type: "supports" },
    { source_knowledge_id: 4, target_knowledge_id: 2, relation_type: "prerequisite" },
    { source_knowledge_id: 1, target_knowledge_id: 3, relation_type: "similarity" },
    { source_knowledge_id: 1, target_knowledge_id: 5 },
    { source_knowledge_id: 1, target_knowledge_id: 999, relation_type: "supports" }
  ]
});
assert.equal(safeGraphRole({ type: "exercise", graph_role: "backbone" }), "assessment");
assert.equal(safeGraphRole({ type: "just-a-statement", graph_role: "backbone" }), "fragment");
assert.equal(normalized.nodes.find(node => node.knowledge_id === 2).graph_role, "assessment");
assert.equal(normalized.nodes.find(node => node.knowledge_id === 3).graph_role, "fragment");
assert.deepEqual(normalized.edges.map(edge => [edge.source_knowledge_id, edge.target_knowledge_id]), [[1, 4], [4, 2]], "invalid and similarity links are not graph dependencies");

const focused = boundedNeighborhood(normalized, 1);
assert.deepEqual(focused.nodes.map(node => node.knowledge_id), [1, 2, 4], "disconnected records are not filled into the focused view");
assert.equal(focused.hiddenCount, 2);

const edgeEmpty = boundedNeighborhood(normalizeGraph({
  focus_knowledge_id: 7,
  nodes: [{ knowledge_id: 6 }, { knowledge_id: 7 }, { knowledge_id: 8 }],
  edges: []
}), 7);
assert.deepEqual(edgeEmpty.nodes.map(node => node.knowledge_id), [7], "edge-empty input remains an honest single focus");
assert.equal(edgeEmpty.edges.length, 0);

const positions = graphLayout(focused.nodes, focused.edges);
assert(positions.get(1).rank < positions.get(4).rank);
assert(positions.get(4).rank < positions.get(2).rank, "supplied edge direction determines rank");
assert(positions.get(4).y < positions.get(1).y);
assert(positions.get(2).y < positions.get(4).y, "later supplied targets are visually above their sources");

// The client consumes this exact server-supplied book_order_v1 spine+fan. It
// neither derives these links from array order nor promotes Exercise/JAS.
const projectionGraph = normalizeGraph({
  focus_knowledge_id: 101,
  nodes: [
    { knowledge_id: 101, label: "A", type: "definition", graph_role: "backbone", source_order: [1] },
    { knowledge_id: 102, label: "B", type: "example", graph_role: "support", source_order: [2] },
    { knowledge_id: 103, label: "C", type: "exercise", graph_role: "backbone", source_order: [3] },
    { knowledge_id: 104, label: "D", type: "theorem", graph_role: "backbone", source_order: [4] },
    { knowledge_id: 105, label: "E", type: "JAS", graph_role: "backbone", source_order: [5] }
  ],
  edges: [
    { source_knowledge_id: 101, target_knowledge_id: 102, relation_type: "book_order_v1" },
    { source_knowledge_id: 101, target_knowledge_id: 103, relation_type: "book_order_v1" },
    { source_knowledge_id: 101, target_knowledge_id: 104, relation_type: "book_order_v1" },
    { source_knowledge_id: 104, target_knowledge_id: 105, relation_type: "book_order_v1" }
  ]
});
const projectionAudit = inspectBookOrderProjection(projectionGraph.nodes, projectionGraph.edges);
assert(projectionGraph.edges.every(edge => isBookOrderProjection(edge.relation_type)));
assert.deepEqual(
  projectionAudit.projectionEdges.map(edge => [edge.source_knowledge_id, edge.target_knowledge_id]),
  [[101, 102], [101, 103], [101, 104], [104, 105]],
  "the exact supplied A→B, A→C, A→D, D→E projection is retained"
);
assert.deepEqual([...new Set(projectionAudit.projectionEdges.map(edge => edge.source_knowledge_id))], [101, 104], "only A and D anchor the supplied projection");
assert.equal(projectionGraph.nodes.find(node => node.knowledge_id === 103).graph_role, "assessment");
assert.equal(projectionGraph.nodes.find(node => node.knowledge_id === 105).graph_role, "fragment");
assert.deepEqual(projectionAudit.invalidAnchorSources, []);
assert.equal(projectionAudit.hasCycle, false);
assert.deepEqual(projectionAudit.strictForwardViolations, []);
assert.deepEqual(projectionAudit.stableTieViolations, []);

const projectionPositions = graphLayout(projectionGraph.nodes, projectionGraph.edges, 1000, 560);
const shuffledProjectionPositions = graphLayout(
  [...projectionGraph.nodes].reverse(),
  [...projectionGraph.edges].reverse(),
  1000,
  560
);
const projectionCenterX = 500;
for (const node of projectionGraph.nodes) {
  assert.deepEqual(
    shuffledProjectionPositions.get(node.knowledge_id),
    projectionPositions.get(node.knowledge_id),
    `placement for ${node.label} is independent of response array order`
  );
}
assert.equal(projectionPositions.get(101).x, projectionCenterX);
assert.equal(projectionPositions.get(104).x, projectionCenterX, "A and D share the central backbone lane");
assert(projectionPositions.get(102).x < projectionCenterX);
assert(projectionPositions.get(103).x > projectionCenterX, "B and C alternate across the A fan");
assert.notEqual(projectionPositions.get(103).x, projectionCenterX, "Exercise stays off the backbone lane");
assert.notEqual(projectionPositions.get(105).x, projectionCenterX, "JAS stays off the backbone lane");
for (const edge of projectionGraph.edges) {
  assert(
    projectionPositions.get(edge.target_knowledge_id).y < projectionPositions.get(edge.source_knowledge_id).y,
    `target ${edge.target_knowledge_id} is above source ${edge.source_knowledge_id}`
  );
}
const projectionCards = projectionGraph.nodes.map(node => ({
  id: node.knowledge_id,
  ...projectionPositions.get(node.knowledge_id)
}));
for (let leftIndex = 0; leftIndex < projectionCards.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < projectionCards.length; rightIndex += 1) {
    const left = projectionCards[leftIndex];
    const right = projectionCards[rightIndex];
    const overlaps = Math.abs(left.x - right.x) < 172 && Math.abs(left.y - right.y) < 68;
    assert.equal(overlaps, false, `cards ${left.id} and ${right.id} do not overlap`);
  }
}

const leadingPrefix = normalizeGraph({
  nodes: [
    { knowledge_id: 90, type: "remark", graph_role: "support", source_order: [0] },
    { knowledge_id: 101, type: "definition", graph_role: "backbone", source_order: [1] }
  ],
  edges: [{ source_knowledge_id: 90, target_knowledge_id: 101, relation_type: "book_order_v1" }]
});
assert.deepEqual(inspectBookOrderProjection(leadingPrefix.nodes, leadingPrefix.edges).invalidAnchorSources, [], "a supplied non-assessment leading-prefix anchor remains valid");

const stableTie = normalizeGraph({
  nodes: [
    { knowledge_id: 201, graph_role: "backbone", source_order: [7] },
    { knowledge_id: 202, graph_role: "backbone", source_order: [7] }
  ],
  edges: [{ source_knowledge_id: 201, target_knowledge_id: 202, relation_type: "book_order_v1" }]
});
assert.deepEqual(inspectBookOrderProjection(stableTie.nodes, stableTie.edges).stableTieViolations, [], "knowledge ID is a stable forward tie-break");
const reversedTie = normalizeGraph({
  nodes: stableTie.nodes,
  edges: [{ source_knowledge_id: 202, target_knowledge_id: 201, relation_type: "book_order_v1" }]
});
const reversedTieAudit = inspectBookOrderProjection(reversedTie.nodes, reversedTie.edges);
assert.equal(reversedTieAudit.stableTieViolations.length, 1);
assert.equal(reversedTieAudit.strictForwardViolations.length, 1);

const cyclicProjection = normalizeGraph({
  nodes: projectionGraph.nodes,
  edges: [
    ...projectionGraph.edges,
    { source_knowledge_id: 105, target_knowledge_id: 101, relation_type: "book_order_v1" }
  ]
});
const cyclicAudit = inspectBookOrderProjection(cyclicProjection.nodes, cyclicProjection.edges);
assert.equal(cyclicAudit.hasCycle, true);
assert.deepEqual(cyclicAudit.invalidAnchorSources, [105], "JAS cannot anchor a supplied projection");

const chainNodes = Array.from({ length: 21 }, (_, index) => ({ knowledge_id: 300 + index, graph_role: "backbone" }));
const chainEdges = chainNodes.slice(1).map((node, index) => ({
  source_knowledge_id: chainNodes[index].knowledge_id,
  target_knowledge_id: node.knowledge_id,
  relation_type: "book_order_v1"
}));
const initialChainPositions = graphLayout(chainNodes, chainEdges, 1000, 560);
const chainRankCount = new Set([...initialChainPositions.values()].map(position => position.rank)).size;
const chainCanvasWidth = graphCanvasWidthForSideLanes(0);
const chainCanvasHeight = graphCanvasHeightForRanks(chainRankCount, 1);
const spacedChainPositions = graphLayout(chainNodes, chainEdges, chainCanvasWidth, chainCanvasHeight);
const chainCoordinates = chainNodes.map(node => spacedChainPositions.get(node.knowledge_id));
assert.equal(chainCanvasWidth, 1000);
assert.equal(chainCanvasHeight, 2760);
assert(chainCoordinates.every(position => position.x === 500), "the entire backbone stays on the central x lane");
assert(chainCoordinates.slice(1).every((position, index) => chainCoordinates[index].y - position.y >= 128), "directed ranks retain at least 128px upward spacing");

const manyNodes = Array.from({ length: MAX_GRAPH_NODES + 25 }, (_, index) => ({
  knowledge_id: index + 1,
  graph_role: "backbone",
  type: "theorem"
}));
const manyEdges = Array.from({ length: manyNodes.length - 1 }, (_, index) => ({
  source_knowledge_id: index + 1,
  target_knowledge_id: index + 2,
  relation_type: "prerequisite"
}));
const capped = normalizeGraph({ nodes: manyNodes, edges: manyEdges, focus_knowledge_id: 1 });
assert.equal(capped.nodes.length, MAX_GRAPH_NODES);
assert.equal(boundedNeighborhood(capped, 1).nodes.length, MAX_RENDERED_GRAPH_NODES);

const graphComponentSource = await readFile(new URL("../src/components/KnowledgeGraph.vue", import.meta.url), "utf8");
assert.match(graphComponentSource, /FOCUS_VERTICAL_ANCHOR = 0\.72/);
assert.match(graphComponentSource, /ref="graphViewport"/);
assert.match(graphComponentSource, /viewport\.scrollTop =/);
assert.match(
  graphComponentSource,
  /\[effectiveStatus, focusId, view, canvasWidth, canvasHeight\]/,
  "focus reveal reruns for ready state, selection, replacement slices, and layout changes"
);

console.log("graph-contents: assertions passed");
