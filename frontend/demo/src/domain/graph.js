export const MAX_GRAPH_NODES = 150;
export const MAX_RENDERED_GRAPH_NODES = 80;
export const DEFAULT_FAN_ITEMS_PER_ANCHOR = 2;
export const MAX_FAN_ITEMS_PER_ANCHOR = 8;
export const DEFAULT_PROJECTION_CHUNK_SIZE = 100;
export const PROJECTION_ROW_HEIGHT = 128;
export const PROJECTION_TOP_PADDING = 100;
export const PROJECTION_BOTTOM_PADDING = 100;

const SEMANTIC_ROLES = new Set(["backbone", "support", "assessment", "fragment", "crosslink"]);
const ASSESSMENT_TYPES = new Set(["exercise"]);
const FRAGMENT_TYPES = new Set(["jas", "just a statement"]);
const SIMILARITY_RELATIONS = new Set([
  "similar", "similarity", "embedding similarity", "nearest neighbor", "nearest neighbour", "cosine"
]);
const SIDE_LANE_SPACING = 200;
const BACKBONE_STACK_SPACING = 112;
const VERTICAL_RANK_SPACING = 128;

function integer(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function normalizedWords(value) {
  return String(value || "").trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}

export function canonicalKnowledgeType(value) {
  return String(value || "").trim().toLowerCase();
}

export function isProjectionBackboneType(value) {
  return ["definition", "theorem", "notation"].includes(canonicalKnowledgeType(value));
}

export function safeGraphRole(node = {}) {
  const type = canonicalKnowledgeType(node.type);
  const semanticType = normalizedWords(node.type);
  if (isProjectionBackboneType(type)) return "backbone";
  if (ASSESSMENT_TYPES.has(semanticType)) return "assessment";
  if (FRAGMENT_TYPES.has(semanticType)) return "fragment";
  const supplied = normalizedWords(node.graph_role);
  if (supplied === "backbone") return "support";
  return SEMANTIC_ROLES.has(supplied) ? supplied : "support";
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
 * Keep the server-supplied book-order projection compact without changing it.
 * Only real main-anchor -> non-main projection targets are folded; the focused
 * item is always retained and no edge or role is inferred from record order.
 */
export function compactBookOrderFans(
  graphView,
  focusId,
  fanLimits = {},
  defaultLimit = DEFAULT_FAN_ITEMS_PER_ANCHOR
) {
  const nodes = Array.isArray(graphView?.nodes) ? graphView.nodes : [];
  const edges = Array.isArray(graphView?.edges) ? graphView.edges : [];
  const byId = new Map(nodes.map(node => [node.knowledge_id, node]));
  const targetsByAnchor = new Map();

  for (const edge of edges) {
    if (!isBookOrderProjection(edge.relation_type)) continue;
    const source = byId.get(edge.source_knowledge_id);
    const target = byId.get(edge.target_knowledge_id);
    if (!source || !target) continue;
    if (safeGraphRole(source) !== "backbone" || safeGraphRole(target) === "backbone") continue;
    if (!targetsByAnchor.has(source.knowledge_id)) targetsByAnchor.set(source.knowledge_id, []);
    targetsByAnchor.get(source.knowledge_id).push(target);
  }

  const retained = new Set(nodes.map(node => node.knowledge_id));
  const hiddenByAnchor = new Map();
  const roleRank = { support: 0, crosslink: 1, unclassified: 2, assessment: 3, fragment: 4 };
  const selectedId = Number(focusId);

  for (const [anchorId, rawTargets] of targetsByAnchor) {
    const targets = [...rawTargets].sort((left, right) => compareNodesForLayout(left, right, roleRank));
    const configuredLimit = Number(fanLimits?.[anchorId]);
    const limit = Math.max(
      1,
      Math.min(
        MAX_FAN_ITEMS_PER_ANCHOR,
        Number.isFinite(configuredLimit) ? Math.floor(configuredLimit) : Math.floor(defaultLimit)
      )
    );
    const visible = targets.slice(0, limit);
    const focusedTarget = targets.find(node => node.knowledge_id === selectedId);
    if (focusedTarget && !visible.some(node => node.knowledge_id === selectedId)) {
      visible[Math.max(0, visible.length - 1)] = focusedTarget;
    }
    const visibleIds = new Set(visible.map(node => node.knowledge_id));
    const hidden = targets.filter(node => !visibleIds.has(node.knowledge_id));
    for (const node of hidden) retained.delete(node.knowledge_id);
    if (hidden.length) hiddenByAnchor.set(anchorId, hidden.length);
  }

  return {
    ...graphView,
    nodes: nodes
      .filter(node => retained.has(node.knowledge_id))
      .map(node => hiddenByAnchor.has(node.knowledge_id)
        ? { ...node, collapsed_fan_count: hiddenByAnchor.get(node.knowledge_id) }
        : node),
    edges: edges.filter(edge => retained.has(edge.source_knowledge_id) && retained.has(edge.target_knowledge_id)),
    hiddenFanCount: [...hiddenByAnchor.values()].reduce((total, count) => total + count, 0)
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

function nonNegativeInteger(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
}

function finiteNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function entriesFromPositions(rawPositions) {
  if (rawPositions instanceof Map) return [...rawPositions.entries()];
  if (Array.isArray(rawPositions)) {
    return rawPositions.map((position, index) => [position?.knowledge_id ?? position?.id ?? index, position]);
  }
  if (rawPositions && typeof rawPositions === "object") return Object.entries(rawPositions);
  return [];
}

function normalizedProjectionPosition(raw = {}, fallbackId = null, chunkSize = DEFAULT_PROJECTION_CHUNK_SIZE) {
  const knowledgeId = integer(raw?.knowledge_id ?? raw?.id ?? fallbackId);
  const index = nonNegativeInteger(raw?.projection_index ?? raw?.index ?? raw?.book_index);
  if (knowledgeId == null || index == null) return null;
  const explicitChunk = nonNegativeInteger(raw?.chunk_index ?? raw?.chunk);
  const anchorId = integer(raw?.anchor_knowledge_id ?? raw?.anchor_id ?? raw?.anchor);
  return {
    ...raw,
    knowledge_id: knowledgeId,
    index,
    projection_index: index,
    chunk_index: explicitChunk ?? Math.floor(index / chunkSize),
    anchor_knowledge_id: anchorId,
    anchor_index: nonNegativeInteger(raw?.anchor_index),
    fan_index: nonNegativeInteger(raw?.fan_index ?? raw?.branch_index),
    stored_lane: finiteNumber(raw?.lane ?? raw?.side_lane),
    x: finiteNumber(raw?.x),
    y: finiteNumber(raw?.y),
    type: canonicalKnowledgeType(raw?.type)
  };
}

function assignCompactProjectionFanLanes(positions) {
  const fanGroups = new Map();
  let maxDepth = 0;
  for (const position of positions.values()) {
    if (isProjectionBackboneType(position.type)) {
      position.fan_index = null;
      position.fan_ordinal = null;
      position.lane = 0;
      continue;
    }
    if (position.anchor_knowledge_id == null) {
      // An unanchored prefix remains off-spine without becoming one enormous fan.
      position.fan_index = 0;
      position.fan_ordinal = 0;
      position.lane = alternatingLane(0);
      maxDepth = Math.max(maxDepth, 1);
      continue;
    }
    if (!fanGroups.has(position.anchor_knowledge_id)) fanGroups.set(position.anchor_knowledge_id, []);
    fanGroups.get(position.anchor_knowledge_id).push(position);
  }

  for (const fan of fanGroups.values()) {
    fan.sort((left, right) => {
      const leftFanIndex = left.fan_index ?? Number.MAX_SAFE_INTEGER;
      const rightFanIndex = right.fan_index ?? Number.MAX_SAFE_INTEGER;
      return leftFanIndex - rightFanIndex || left.index - right.index || left.knowledge_id - right.knowledge_id;
    });
    fan.forEach((position, ordinal) => {
      // `fan_index` is the canonical compact per-anchor ordinal. Keep the old
      // internal name as an alias while adapters move to the canonical field.
      position.fan_index = ordinal;
      position.fan_ordinal = ordinal;
      position.lane = alternatingLane(ordinal);
      maxDepth = Math.max(maxDepth, Math.abs(position.lane));
    });
  }
  return maxDepth;
}

function projectionManifestSource(raw = {}) {
  const hasCanonicalTopLevel = [
    "projection_revision",
    "book_revision",
    "total_nodes",
    "chunk_size",
    "positions",
    "initial_chunk"
  ].some(field => Object.prototype.hasOwnProperty.call(raw || {}, field));
  return hasCanonicalTopLevel ? raw : (raw?.manifest || raw || {});
}

/**
 * Normalize the immutable, server-authored projection manifest. The manifest is
 * the only source of global order, anchor and chunk membership. Nothing here
 * creates a relation or infers an anchor from neighbouring records.
 */
export function normalizeProjectionManifest(raw = {}) {
  const source = projectionManifestSource(raw);
  const requestedChunkSize = nonNegativeInteger(source?.chunk_size);
  const chunkSize = Math.max(1, requestedChunkSize || DEFAULT_PROJECTION_CHUNK_SIZE);
  const positions = new Map();
  let largestIndex = -1;
  for (const [key, value] of entriesFromPositions(source?.positions)) {
    const position = normalizedProjectionPosition(value, key, chunkSize);
    if (!position || positions.has(position.knowledge_id)) continue;
    positions.set(position.knowledge_id, position);
    largestIndex = Math.max(largestIndex, position.index);
  }
  const maxFanDepth = assignCompactProjectionFanLanes(positions);

  const declaredTotal = nonNegativeInteger(source?.total_nodes);
  const totalNodes = Math.max(declaredTotal ?? 0, largestIndex + 1);
  const chunkCount = totalNodes ? Math.ceil(totalNodes / chunkSize) : 0;
  const declaredInitial = nonNegativeInteger(source?.initial_chunk) ?? 0;
  const initialChunk = chunkCount ? Math.min(chunkCount - 1, declaredInitial) : 0;
  const sideLaneSpacing = Math.max(172, finiteNumber(source?.side_lane_spacing) || SIDE_LANE_SPACING);
  const width = Math.ceil(Math.max(1000, 2 * (110 + maxFanDepth * sideLaneSpacing)));
  const rowHeight = Math.max(96, finiteNumber(source?.row_height) || PROJECTION_ROW_HEIGHT);
  const topPadding = Math.max(68, finiteNumber(source?.top_padding) || PROJECTION_TOP_PADDING);
  const bottomPadding = Math.max(68, finiteNumber(source?.bottom_padding) || PROJECTION_BOTTOM_PADDING);
  const computedHeight = topPadding + bottomPadding + Math.max(0, totalNodes - 1) * rowHeight;
  const totalHeight = Math.max(computedHeight, finiteNumber(source?.total_height) || 0);

  return {
    projection_revision: source?.projection_revision == null ? null : String(source.projection_revision),
    book_revision: source?.book_revision == null ? null : String(source.book_revision),
    total_nodes: totalNodes,
    chunk_size: chunkSize,
    chunk_count: chunkCount,
    initial_chunk: initialChunk,
    positions,
    width,
    max_fan_depth: maxFanDepth,
    row_height: rowHeight,
    top_padding: topPadding,
    bottom_padding: bottomPadding,
    total_height: totalHeight,
    center_x: width / 2,
    side_lane_spacing: sideLaneSpacing
  };
}

export function projectionChunkIndexForKnowledge(manifest, knowledgeId) {
  const normalized = manifest?.positions instanceof Map ? manifest : normalizeProjectionManifest(manifest);
  return normalized.positions.get(Number(knowledgeId))?.chunk_index ?? null;
}

export function projectionChunkWindow(centerChunk, manifest, radius = 1) {
  const normalized = manifest?.positions instanceof Map ? manifest : normalizeProjectionManifest(manifest);
  if (!normalized.chunk_count) return [];
  const center = Math.max(0, Math.min(
    normalized.chunk_count - 1,
    nonNegativeInteger(centerChunk) ?? normalized.initial_chunk
  ));
  const boundedRadius = Math.max(0, Math.floor(Number(radius) || 0));
  const chunks = [];
  for (let index = center - boundedRadius; index <= center + boundedRadius; index += 1) {
    if (index >= 0 && index < normalized.chunk_count) chunks.push(index);
  }
  return chunks;
}

function projectionChunkMap(projection) {
  if (projection?.chunks instanceof Map) return projection.chunks;
  if (Array.isArray(projection?.chunks)) return new Map(
    projection.chunks.map((chunk, index) => [nonNegativeInteger(chunk?.chunk_index) ?? index, chunk])
  );
  if (projection?.chunks && typeof projection.chunks === "object") {
    return new Map(Object.entries(projection.chunks).map(([index, chunk]) => [Number(index), chunk]));
  }
  return new Map();
}

export function hasProjectionChunk(projection, chunkIndex) {
  const index = nonNegativeInteger(chunkIndex);
  return index != null && projectionChunkMap(projection).has(index);
}

function alternatingLane(ordinal) {
  const value = Math.max(0, Math.floor(Number(ordinal) || 0));
  const magnitude = Math.floor(value / 2) + 1;
  return (value % 2 === 0 ? -1 : 1) * magnitude;
}

/** Fixed full-book coordinates: later projection indices are always above earlier ones. */
export function projectionPosition(rawNode = {}, manifest) {
  const normalized = manifest?.positions instanceof Map ? manifest : normalizeProjectionManifest(manifest);
  const stored = normalized.positions.get(Number(rawNode?.knowledge_id));
  if (!stored) return null;
  const type = canonicalKnowledgeType(rawNode?.type) || canonicalKnowledgeType(stored.type);
  const backbone = isProjectionBackboneType(type);
  let lane = backbone ? 0 : stored.lane;
  if (!backbone && (!Number.isFinite(lane) || lane === 0)) {
    lane = alternatingLane(stored.fan_index ?? stored.fan_ordinal ?? 0);
  }
  const x = backbone
    ? normalized.center_x
    : normalized.center_x + lane * normalized.side_lane_spacing;
  const y = normalized.total_height - normalized.bottom_padding - stored.index * normalized.row_height;
  return { x, y, lane, index: stored.index, chunk_index: stored.chunk_index };
}

function normalizeProjectionNode(raw = {}, manifest) {
  const knowledgeId = integer(raw?.knowledge_id);
  const stored = manifest.positions.get(knowledgeId);
  if (knowledgeId == null || !stored) return null;
  const type = canonicalKnowledgeType(raw?.type) || canonicalKnowledgeType(stored.type) || "knowledge";
  const position = projectionPosition({ ...raw, knowledge_id: knowledgeId, type }, manifest);
  if (!position) return null;
  return {
    ...raw,
    knowledge_id: knowledgeId,
    label: String(raw?.label || raw?.statement || type || `Knowledge ${knowledgeId}`),
    type,
    graph_role: safeGraphRole({ ...raw, type }),
    anchor_knowledge_id: stored.anchor_knowledge_id,
    projection_index: stored.index,
    chunk_index: stored.chunk_index,
    position
  };
}

function normalizeProjectionEdge(raw = {}, knownTypes) {
  const edgeId = String(raw?.edge_id || "").trim();
  const source = integer(raw?.source_knowledge_id);
  const target = integer(raw?.target_knowledge_id);
  if (!edgeId || source == null || target == null || source === target) return null;
  if (!isBookOrderProjection(raw?.relation_type)) return null;
  // A side item, including a leading pre-spine item, is never a projection anchor.
  if (!isProjectionBackboneType(knownTypes.get(source))) return null;
  return {
    ...raw,
    edge_id: edgeId,
    source_knowledge_id: source,
    target_knowledge_id: target,
    relation_type: "book_order_v1"
  };
}

/**
 * Merge only explicitly loaded chunks. Nodes retain their global coordinates;
 * edges retain their server IDs and are never synthesized by the client.
 */
export function mergeProjectionChunks(projection = {}, chunkIndices = []) {
  const manifest = normalizeProjectionManifest(projection);
  const chunks = projectionChunkMap(projection);
  const requested = [...new Set(chunkIndices.map(nonNegativeInteger).filter(index => index != null))];
  const nodeById = new Map();
  const knownTypes = new Map(
    [...manifest.positions].map(([id, position]) => [id, canonicalKnowledgeType(position.type)])
  );

  for (const index of requested) {
    const chunk = chunks.get(index);
    for (const raw of Array.isArray(chunk?.nodes) ? chunk.nodes : []) {
      const node = normalizeProjectionNode(raw, manifest);
      if (!node || nodeById.has(node.knowledge_id)) continue;
      nodeById.set(node.knowledge_id, node);
      knownTypes.set(node.knowledge_id, node.type);
    }
  }

  const edgeById = new Map();
  for (const index of requested) {
    const chunk = chunks.get(index);
    for (const raw of Array.isArray(chunk?.edges) ? chunk.edges : []) {
      const edge = normalizeProjectionEdge(raw, knownTypes);
      if (!edge || edgeById.has(edge.edge_id)) continue;
      if (!nodeById.has(edge.source_knowledge_id) || !nodeById.has(edge.target_knowledge_id)) continue;
      edgeById.set(edge.edge_id, edge);
    }
  }

  return {
    manifest,
    nodes: [...nodeById.values()].sort((left, right) => left.projection_index - right.projection_index),
    edges: [...edgeById.values()],
    chunk_indices: requested,
    projection_revision: manifest.projection_revision,
    book_revision: manifest.book_revision
  };
}

export function projectionChunkAtScroll(manifest, scrollTop, viewportHeight = 0) {
  const normalized = manifest?.positions instanceof Map ? manifest : normalizeProjectionManifest(manifest);
  if (!normalized.total_nodes) return null;
  const viewportMiddle = Math.max(0, Number(scrollTop) || 0) + Math.max(0, Number(viewportHeight) || 0) / 2;
  const rawIndex = Math.round(
    (normalized.total_height - normalized.bottom_padding - viewportMiddle) / normalized.row_height
  );
  const index = Math.max(0, Math.min(normalized.total_nodes - 1, rawIndex));
  return Math.floor(index / normalized.chunk_size);
}

export function projectionScrollTopForKnowledge(manifest, knowledgeId, viewportHeight = 0, anchor = 0.72) {
  const normalized = manifest?.positions instanceof Map ? manifest : normalizeProjectionManifest(manifest);
  const position = projectionPosition({
    knowledge_id: Number(knowledgeId),
    type: normalized.positions.get(Number(knowledgeId))?.type
  }, normalized);
  if (!position) return null;
  const height = Math.max(0, Number(viewportHeight) || 0);
  const desired = position.y - height * Math.max(0, Math.min(1, Number(anchor) || 0));
  return Math.max(0, Math.min(Math.max(0, normalized.total_height - height), desired));
}
