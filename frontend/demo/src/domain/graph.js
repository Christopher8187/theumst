export const MAX_GRAPH_NODES = 150;
export const MAX_RENDERED_GRAPH_NODES = 80;

const SEMANTIC_ROLES = new Set(["backbone", "support", "assessment", "fragment", "crosslink"]);
const ASSESSMENT_TYPES = new Set(["exercise"]);
const FRAGMENT_TYPES = new Set(["jas", "just a statement"]);
const SIMILARITY_RELATIONS = new Set([
  "similar", "similarity", "embedding similarity", "nearest neighbor", "nearest neighbour", "cosine"
]);
const SIDE_LANE_SPACING = 220;
const BACKBONE_STACK_SPACING = 112;
const VERTICAL_RANK_SPACING = 128;

function integer(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function normalizedWords(value) {
  return String(value || "").trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}

export function safeGraphRole(node = {}) {
  const type = normalizedWords(node.type);
  if (ASSESSMENT_TYPES.has(type)) return "assessment";
  if (FRAGMENT_TYPES.has(type)) return "fragment";
  const supplied = normalizedWords(node.graph_role);
  return SEMANTIC_ROLES.has(supplied) ? supplied : "unclassified";
}

export function isSimilarityRelation(relationType) {
  const normalized = normalizedWords(relationType);
  return SIMILARITY_RELATIONS.has(normalized)
    || normalized.startsWith("similarity ")
    || normalized.startsWith("embedding similar");
}

export function isBookOrderProjection(relationType) {
  return normalizedWords(relationType) === "book order v1";
}

export function graphCanvasWidthForSideLanes(
  sideLaneCount,
  minimumWidth = 1000,
  laneSpacing = SIDE_LANE_SPACING,
  sidePadding = 110
) {
  const count = Math.max(0, Math.floor(Number(sideLaneCount) || 0));
  const minimum = Math.max(sidePadding * 2, Number(minimumWidth) || 1000);
  const spacing = Math.max(172, Number(laneSpacing) || 220);
  return Math.ceil(Math.max(minimum, 2 * (sidePadding + count * spacing)));
}

export function graphCanvasHeightForRanks(
  rankCount,
  maxBackbonePerRank = 1,
  minimumHeight = 560,
  rankSpacing = VERTICAL_RANK_SPACING,
  stackSpacing = BACKBONE_STACK_SPACING,
  verticalPadding = 100
) {
  const count = Math.max(1, Math.floor(Number(rankCount) || 1));
  const centralStack = Math.max(1, Math.floor(Number(maxBackbonePerRank) || 1));
  const rankStep = Math.max(96, Number(rankSpacing) || 128) + (centralStack - 1) * stackSpacing;
  const stackHeight = (centralStack - 1) * stackSpacing;
  return Math.ceil(Math.max(
    Number(minimumHeight) || 560,
    verticalPadding * 2 + (count - 1) * rankStep + stackHeight
  ));
}

function canonicalOrderParts(node = {}) {
  const raw = node.book_order_v1 ?? node.book_order ?? node.projection_order ?? node.source_order;
  if (raw == null) return null;
  const values = Array.isArray(raw) ? raw : String(raw).split(/[.\s/:]+/).filter(Boolean);
  return values.map(value => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : String(value);
  });
}

function compareOrderParts(left, right) {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const a = left[index];
    const b = right[index];
    if (typeof a === "number" && typeof b === "number" && a !== b) return a - b;
    const compared = String(a).localeCompare(String(b), "en", { numeric: true });
    if (compared) return compared;
  }
  return left.length - right.length;
}

function compareNodesForLayout(left, right, roleRank) {
  const leftOrder = canonicalOrderParts(left);
  const rightOrder = canonicalOrderParts(right);
  if (leftOrder && rightOrder) {
    const orderDifference = compareOrderParts(leftOrder, rightOrder);
    if (orderDifference) return orderDifference;
  } else if (leftOrder || rightOrder) {
    return leftOrder ? -1 : 1;
  }
  const roleDifference = (roleRank[left.graph_role] ?? 2) - (roleRank[right.graph_role] ?? 2);
  return roleDifference || left.knowledge_id - right.knowledge_id;
}

function projectionHasCycle(edges) {
  const outgoing = new Map();
  for (const edge of edges) {
    if (!outgoing.has(edge.source_knowledge_id)) outgoing.set(edge.source_knowledge_id, []);
    outgoing.get(edge.source_knowledge_id).push(edge.target_knowledge_id);
  }
  const state = new Map();
  function visit(id) {
    if (state.get(id) === 1) return true;
    if (state.get(id) === 2) return false;
    state.set(id, 1);
    for (const target of outgoing.get(id) || []) if (visit(target)) return true;
    state.set(id, 2);
    return false;
  }
  return [...outgoing.keys()].some(visit);
}

/**
 * Audit only the projection edges supplied by the server. This never creates or
 * repairs an edge; forward/tie checks are skipped when canonical order metadata
 * is not present on both endpoints.
 */
export function inspectBookOrderProjection(nodes = [], edges = []) {
  const byId = new Map(nodes.map(node => [node.knowledge_id, node]));
  const projectionEdges = edges.filter(edge => isBookOrderProjection(edge.relation_type));
  const invalidAnchorSources = new Set();
  const strictForwardViolations = [];
  const stableTieViolations = [];

  for (const edge of projectionEdges) {
    const source = byId.get(edge.source_knowledge_id);
    const target = byId.get(edge.target_knowledge_id);
    if (!source || !target) continue;
    if (["assessment", "fragment"].includes(safeGraphRole(source))) {
      invalidAnchorSources.add(source.knowledge_id);
    }
    const sourceOrder = canonicalOrderParts(source);
    const targetOrder = canonicalOrderParts(target);
    if (!sourceOrder || !targetOrder) continue;
    const orderComparison = compareOrderParts(sourceOrder, targetOrder);
    const stableComparison = orderComparison || (source.knowledge_id - target.knowledge_id);
    if (stableComparison >= 0) strictForwardViolations.push(edge);
    if (orderComparison === 0 && source.knowledge_id >= target.knowledge_id) {
      stableTieViolations.push(edge);
    }
  }

  return {
    projectionEdges,
    hasCycle: projectionHasCycle(projectionEdges),
    invalidAnchorSources: [...invalidAnchorSources].sort((a, b) => a - b),
    strictForwardViolations,
    stableTieViolations
  };
}

/** Normalize the frozen graph contract without deriving or inferring any edges. */
export function normalizeGraph(payload = {}, fallbackFocus = null) {
  const rawNodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
  const seen = new Set();
  const nodes = [];
  for (const raw of rawNodes) {
    const knowledgeId = integer(raw?.knowledge_id);
    if (knowledgeId == null || seen.has(knowledgeId) || nodes.length >= MAX_GRAPH_NODES) continue;
    seen.add(knowledgeId);
    nodes.push({
      ...raw,
      knowledge_id: knowledgeId,
      label: String(raw.label || raw.statement || raw.type || `Knowledge ${knowledgeId}`),
      type: normalizedWords(raw.type) || "knowledge",
      graph_role: safeGraphRole(raw),
      collapsed_ancestor_count: Math.max(0, integer(raw.collapsed_ancestor_count) || 0),
      collapsed_descendant_count: Math.max(0, integer(raw.collapsed_descendant_count) || 0)
    });
  }

  const edgeSeen = new Set();
  const edges = [];
  for (const raw of Array.isArray(payload?.edges) ? payload.edges : []) {
    const source = integer(raw?.source_knowledge_id);
    const target = integer(raw?.target_knowledge_id);
    const relationType = normalizedWords(raw?.relation_type);
    if (!seen.has(source) || !seen.has(target) || source === target || !relationType) continue;
    // Nearest-neighbour discovery is an overlay, never a dependency relation.
    if (isSimilarityRelation(relationType)) continue;
    const key = `${source}:${target}:${relationType}`;
    if (edgeSeen.has(key)) continue;
    edgeSeen.add(key);
    edges.push({
      ...raw,
      source_knowledge_id: source,
      target_knowledge_id: target,
      relation_type: relationType
    });
  }

  const responseFocus = integer(payload?.focus_knowledge_id);
  return {
    authored_dependencies: payload?.authored_dependencies === true,
    nodes,
    edges,
    focus_knowledge_id: responseFocus ?? integer(fallbackFocus),
    graph_revision: payload?.graph_revision == null ? null : String(payload.graph_revision),
    truncated: Boolean(payload?.truncated) || rawNodes.length > MAX_GRAPH_NODES
  };
}

export function boundedNeighborhood(graph, focusId, limit = MAX_RENDERED_GRAPH_NODES) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const boundedLimit = Math.max(1, Math.min(MAX_RENDERED_GRAPH_NODES, Number(limit) || MAX_RENDERED_GRAPH_NODES));
  if (!nodes.length) return { nodes: [], edges: [], hiddenCount: 0 };
  const byId = new Map(nodes.map(node => [node.knowledge_id, node]));
  const start = byId.has(Number(focusId)) ? Number(focusId) : nodes[0].knowledge_id;
  const adjacency = new Map(nodes.map(node => [node.knowledge_id, new Set()]));
  for (const edge of edges) {
    adjacency.get(edge.source_knowledge_id)?.add(edge.target_knowledge_id);
    adjacency.get(edge.target_knowledge_id)?.add(edge.source_knowledge_id);
  }

  const chosen = new Set();
  const queued = new Set([start]);
  const queue = [start];
  while (queue.length && chosen.size < boundedLimit) {
    const id = queue.shift();
    if (chosen.has(id)) continue;
    chosen.add(id);
    const neighbors = [...(adjacency.get(id) || [])].sort((a, b) => a - b);
    for (const neighbor of neighbors) {
      if (!chosen.has(neighbor) && !queued.has(neighbor)) {
        queued.add(neighbor);
        queue.push(neighbor);
      }
    }
  }

  return {
    nodes: nodes.filter(node => chosen.has(node.knowledge_id)),
    edges: edges.filter(edge => chosen.has(edge.source_knowledge_id) && chosen.has(edge.target_knowledge_id)),
    hiddenCount: Math.max(0, nodes.length - chosen.size)
  };
}

/**
 * Lay out the supplied directed graph. Upward rank is derived only from the
 * supplied edge direction; graph role affects horizontal lanes, never adjacency.
 */
export function graphLayout(nodes = [], edges = [], width = 1000, height = 560) {
  const ids = new Set(nodes.map(node => node.knowledge_id));
  const incoming = new Map(nodes.map(node => [node.knowledge_id, 0]));
  const outgoing = new Map(nodes.map(node => [node.knowledge_id, []]));
  for (const edge of edges) {
    if (!ids.has(edge.source_knowledge_id) || !ids.has(edge.target_knowledge_id)) continue;
    incoming.set(edge.target_knowledge_id, (incoming.get(edge.target_knowledge_id) || 0) + 1);
    outgoing.get(edge.source_knowledge_id)?.push(edge.target_knowledge_id);
  }
  for (const targets of outgoing.values()) targets.sort((a, b) => a - b);
  const level = new Map(nodes.map(node => [node.knowledge_id, 0]));
  const queue = nodes
    .filter(node => incoming.get(node.knowledge_id) === 0)
    .map(node => node.knowledge_id)
    .sort((a, b) => a - b);
  const visited = new Set();
  while (queue.length) {
    const source = queue.shift();
    if (visited.has(source)) continue;
    visited.add(source);
    for (const target of outgoing.get(source) || []) {
      level.set(target, Math.max(level.get(target) || 0, (level.get(source) || 0) + 1));
      incoming.set(target, incoming.get(target) - 1);
      if (incoming.get(target) === 0) queue.push(target);
    }
    queue.sort((a, b) => a - b);
  }

  // A cycle violates the expected DAG contract. Keep it visible in a final rank
  // rather than silently deleting its real edges or inventing a route through it.
  const fallbackLevel = Math.max(0, ...level.values()) + (visited.size ? 1 : 0);
  for (const node of nodes) if (!visited.has(node.knowledge_id)) level.set(node.knowledge_id, fallbackLevel);

  const ranks = new Map();
  for (const node of nodes) {
    const rank = level.get(node.knowledge_id) || 0;
    if (!ranks.has(rank)) ranks.set(rank, []);
    ranks.get(rank).push(node);
  }
  const orderedRanks = [...ranks.keys()].sort((a, b) => a - b);
  const yStep = orderedRanks.length > 1 ? (height - 200) / (orderedRanks.length - 1) : 0;
  const centerX = width / 2;
  const roleRank = { support: 0, crosslink: 1, unclassified: 2, backbone: 3, assessment: 4, fragment: 5 };
  const positions = new Map();

  orderedRanks.forEach((rank, rankIndex) => {
    const rankNodes = [...ranks.get(rank)].sort((a, b) => compareNodesForLayout(a, b, roleRank));
    const backboneNodes = rankNodes.filter(node => node.graph_role === "backbone");
    const sideNodes = rankNodes.filter(node => node.graph_role !== "backbone");
    const baseY = orderedRanks.length > 1 ? height - 100 - rankIndex * yStep : height / 2;

    backboneNodes.forEach((node, index) => positions.set(node.knowledge_id, {
      x: centerX,
      y: baseY + (index - (backboneNodes.length - 1) / 2) * BACKBONE_STACK_SPACING,
      rank,
      lane: 0
    }));

    sideNodes.forEach((node, index) => {
      const direction = index % 2 === 0 ? -1 : 1;
      const laneMagnitude = Math.floor(index / 2) + 1;
      const lane = direction * laneMagnitude;
      positions.set(node.knowledge_id, {
        x: centerX + lane * SIDE_LANE_SPACING,
        y: baseY,
        rank,
        lane
      });
    });
  });
  return positions;
}
