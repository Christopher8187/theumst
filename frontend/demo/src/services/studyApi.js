import { demoFetch, DemoApiError } from "../api";

const DEFAULT_SIMILAR_LIMIT = 10;
const MAX_SIMILAR_LIMIT = 25;
const normalizedProjectionChunks = new WeakSet();
const normalizedProjectionManifests = new WeakSet();

export class ProjectionContractError extends Error {
  constructor(message) {
    super(message);
    this.name = "ProjectionContractError";
  }
}

function requiredInteger(value, name, minimum = 0) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum) {
    throw new ProjectionContractError(`The learning map returned an invalid ${name}.`);
  }
  return parsed;
}

function requiredRevision(value, name = "revision") {
  if (value == null || String(value).trim() === "") {
    throw new ProjectionContractError(`The learning map did not identify its ${name}.`);
  }
  return String(value);
}

function immutableRecord(value) {
  return Object.freeze({ ...(value || {}) });
}

function hasOwn(value, name) {
  return Object.prototype.hasOwnProperty.call(value || {}, name);
}

function optionalText(value, name) {
  if (value == null) return value;
  if (typeof value !== "string" || value.trim() === "") {
    throw new ProjectionContractError(`The learning map returned an invalid ${name}.`);
  }
  return value;
}

function optionalKnowledgeId(value, name) {
  if (value == null) return value;
  if ((typeof value !== "number" && typeof value !== "string") || String(value).trim() === "") {
    throw new ProjectionContractError(`The learning map returned an invalid ${name}.`);
  }
  return value;
}

function optionalInteger(value, name, minimum = Number.MIN_SAFE_INTEGER) {
  if (value == null) return value;
  return requiredInteger(value, name, minimum);
}

function optionalPositiveNumber(value, name) {
  if (value == null) return value;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new ProjectionContractError(`The learning map returned an invalid ${name}.`);
  }
  return parsed;
}

export function normalizeProjectionChunk(payload, expected = {}) {
  if (payload && normalizedProjectionChunks.has(payload)) {
    if (expected.projectionRevision != null && payload.projection_revision !== String(expected.projectionRevision)) {
      throw new ProjectionContractError("The learning map changed while a section was loading. Please try again.");
    }
    if (expected.chunkIndex != null && payload.chunk_index !== Number(expected.chunkIndex)) {
      throw new ProjectionContractError("The learning map returned a different section than requested.");
    }
    return payload;
  }
  const projectionRevision = requiredRevision(payload?.projection_revision, "projection revision");
  const chunkIndex = requiredInteger(payload?.chunk_index, "chunk index");
  if (expected.projectionRevision != null && projectionRevision !== String(expected.projectionRevision)) {
    throw new ProjectionContractError("The learning map changed while a section was loading. Please try again.");
  }
  if (expected.chunkIndex != null && chunkIndex !== Number(expected.chunkIndex)) {
    throw new ProjectionContractError("The learning map returned a different section than requested.");
  }
  const startIndex = requiredInteger(payload?.start_index, "section start");
  const endIndex = requiredInteger(payload?.end_index, "section end");
  if (endIndex < startIndex) {
    throw new ProjectionContractError("The learning map returned an invalid section range.");
  }
  const normalized = Object.freeze({
    projection_revision: projectionRevision,
    chunk_index: chunkIndex,
    start_index: startIndex,
    end_index: endIndex,
    nodes: Object.freeze((Array.isArray(payload?.nodes) ? payload.nodes : []).map(immutableRecord)),
    edges: Object.freeze((Array.isArray(payload?.edges) ? payload.edges : []).map(immutableRecord))
  });
  normalizedProjectionChunks.add(normalized);
  return normalized;
}

export function normalizeProjectionManifest(payload) {
  if (payload && normalizedProjectionManifests.has(payload)) return payload;
  const projectionRevision = requiredRevision(payload?.projection_revision, "projection revision");
  const bookRevision = requiredRevision(payload?.book_revision, "book revision");
  const totalNodes = requiredInteger(payload?.total_nodes, "item count");
  const chunkSize = requiredInteger(payload?.chunk_size, "section size", 1);
  const positionKeys = new Set();
  const positionIndexes = new Set();
  const positions = Object.freeze((Array.isArray(payload?.positions) ? payload.positions : []).map(position => {
    if (position?.knowledge_id == null) {
      throw new ProjectionContractError("The learning map returned an item without an identifier.");
    }
    const index = requiredInteger(position.index, "item position");
    const key = String(position.knowledge_id);
    if (index >= totalNodes || positionKeys.has(key) || positionIndexes.has(index)) {
      throw new ProjectionContractError("The learning map returned an invalid item position.");
    }
    positionKeys.add(key);
    positionIndexes.add(index);
    const normalizedPosition = { knowledge_id: position.knowledge_id, index };
    if (hasOwn(position, "type")) normalizedPosition.type = optionalText(position.type, "item type");
    if (hasOwn(position, "graph_role")) normalizedPosition.graph_role = optionalText(position.graph_role, "item role");
    if (hasOwn(position, "anchor_knowledge_id")) {
      normalizedPosition.anchor_knowledge_id = optionalKnowledgeId(position.anchor_knowledge_id, "anchor identifier");
    }
    if (hasOwn(position, "anchor_index")) {
      normalizedPosition.anchor_index = optionalInteger(position.anchor_index, "anchor position", 0);
    }
    if (hasOwn(position, "fan_index")) {
      normalizedPosition.fan_index = optionalInteger(position.fan_index, "fan position", 0);
    }
    if (hasOwn(position, "lane")) normalizedPosition.lane = optionalInteger(position.lane, "lane");
    return Object.freeze(normalizedPosition);
  }));
  if (positions.length !== totalNodes) {
    throw new ProjectionContractError("The learning map did not include a position for every item.");
  }
  const initialChunk = payload?.initial_chunk == null
    ? null
    : normalizeProjectionChunk(payload.initial_chunk, { projectionRevision });
  if (totalNodes > 0 && initialChunk == null) {
    throw new ProjectionContractError("The learning map did not include its first section.");
  }
  if (initialChunk && (initialChunk.chunk_index !== 0 || initialChunk.start_index !== 0)) {
    throw new ProjectionContractError("The learning map returned an invalid first section.");
  }
  const normalized = {
    projection_revision: projectionRevision,
    book_revision: bookRevision,
    total_nodes: totalNodes,
    chunk_size: chunkSize,
    positions,
    initial_chunk: initialChunk
  };
  if (hasOwn(payload, "canvas_width")) {
    normalized.canvas_width = optionalPositiveNumber(payload.canvas_width, "canvas width");
  }
  if (hasOwn(payload, "row_height")) {
    normalized.row_height = optionalPositiveNumber(payload.row_height, "row height");
  }
  if (hasOwn(payload, "side_lane_spacing")) {
    normalized.side_lane_spacing = optionalPositiveNumber(payload.side_lane_spacing, "side-lane spacing");
  }
  Object.freeze(normalized);
  normalizedProjectionManifests.add(normalized);
  return normalized;
}

export async function fetchGraphProjectionManifest(grimoireId, options = {}) {
  const payload = await demoFetch(`/api/demo/grimoires/${grimoireId}/graph/projection`, {
    signal: options.signal
  });
  return normalizeProjectionManifest(payload);
}

export async function fetchGraphProjectionChunk(grimoireId, chunkIndex, options = {}) {
  const index = requiredInteger(chunkIndex, "chunk index");
  const payload = await demoFetch(`/api/demo/grimoires/${grimoireId}/graph/projection/chunks/${index}`, {
    signal: options.signal
  });
  return normalizeProjectionChunk(payload, {
    projectionRevision: options.projectionRevision,
    chunkIndex: index
  });
}

function projectionKey(grimoireId, revision) {
  return `${String(grimoireId)}:${String(revision)}`;
}

function projectionSnapshot(entry) {
  if (!entry.snapshot) {
    entry.snapshot = Object.freeze({
      ...entry.manifest,
      chunks: entry.chunks
    });
  }
  return entry.snapshot;
}

export function createProjectionStore(options = {}) {
  const loadManifest = options.fetchManifest || fetchGraphProjectionManifest;
  const loadChunk = options.fetchChunk || fetchGraphProjectionChunk;
  const entries = new Map();
  const activeRevisionByBook = new Map();
  const manifestRequests = new Map();

  function activeEntry(grimoireId) {
    const revision = activeRevisionByBook.get(String(grimoireId));
    return revision == null ? null : entries.get(projectionKey(grimoireId, revision)) || null;
  }

  async function load(grimoireId, loadOptions = {}) {
    const bookKey = String(grimoireId);
    const current = activeEntry(grimoireId);
    if (current && !loadOptions.force) return projectionSnapshot(current);
    if (manifestRequests.has(bookKey)) return manifestRequests.get(bookKey);

    const request = Promise.resolve(loadManifest(grimoireId, loadOptions)).then(rawManifest => {
      const manifest = normalizeProjectionManifest(rawManifest);
      const key = projectionKey(grimoireId, manifest.projection_revision);
      let entry = entries.get(key);
      if (!entry) {
        const chunks = new Map();
        if (manifest.initial_chunk) chunks.set(manifest.initial_chunk.chunk_index, manifest.initial_chunk);
        entry = {
          grimoireId,
          manifest,
          chunks,
          positions: new Map(manifest.positions.map(position => [String(position.knowledge_id), position.index])),
          chunkRequests: new Map(),
          snapshot: null
        };
        entries.set(key, entry);
      }
      activeRevisionByBook.set(bookKey, manifest.projection_revision);
      return projectionSnapshot(entry);
    }).finally(() => manifestRequests.delete(bookKey));

    manifestRequests.set(bookKey, request);
    return request;
  }

  async function ensureChunk(grimoireId, chunkIndex, expectedRevision = null) {
    const index = requiredInteger(chunkIndex, "chunk index");
    const currentProjection = await load(grimoireId);
    const revision = currentProjection.projection_revision;
    if (expectedRevision != null && revision !== String(expectedRevision)) {
      throw new ProjectionContractError("The learning map revision no longer matches this view. Please try again.");
    }
    const entry = entries.get(projectionKey(grimoireId, revision));
    const chunkCount = Math.ceil(entry.manifest.total_nodes / entry.manifest.chunk_size);
    if (index >= chunkCount) {
      throw new ProjectionContractError("The requested learning-map section is outside this book.");
    }
    if (entry.chunks.has(index)) return projectionSnapshot(entry);
    if (entry.chunkRequests.has(index)) return entry.chunkRequests.get(index);

    const request = Promise.resolve(loadChunk(grimoireId, index, {
      projectionRevision: revision
    })).then(rawChunk => {
      const chunk = normalizeProjectionChunk(rawChunk, {
        projectionRevision: revision,
        chunkIndex: index
      });
      if (chunk.projection_revision !== revision || chunk.chunk_index !== index) {
        throw new ProjectionContractError("The learning map changed while a section was loading. Please try again.");
      }
      entry.chunks = new Map(entry.chunks);
      entry.chunks.set(index, chunk);
      entry.snapshot = null;
      return projectionSnapshot(entry);
    }).finally(() => entry.chunkRequests.delete(index));

    entry.chunkRequests.set(index, request);
    return request;
  }

  async function ensureSelection(grimoireId, knowledgeId, expectedRevision = null) {
    const currentProjection = await load(grimoireId);
    if (expectedRevision != null && currentProjection.projection_revision !== String(expectedRevision)) {
      throw new ProjectionContractError("The learning map revision no longer matches this view. Please try again.");
    }
    const entry = entries.get(projectionKey(grimoireId, currentProjection.projection_revision));
    const index = entry.positions.get(String(knowledgeId));
    if (index == null) return projectionSnapshot(entry);
    return ensureChunk(
      grimoireId,
      Math.floor(index / entry.manifest.chunk_size),
      entry.manifest.projection_revision
    );
  }

  return Object.freeze({
    load,
    ensureChunk,
    ensureSelection,
    current(grimoireId) {
      const entry = activeEntry(grimoireId);
      return entry ? projectionSnapshot(entry) : null;
    }
  });
}

export function normalizeSimilarResults(rawResults, selectedKnowledgeId, limit = DEFAULT_SIMILAR_LIMIT) {
  const selectedKey = String(selectedKnowledgeId);
  const seen = new Set();
  return (Array.isArray(rawResults) ? rawResults : [])
    .map(result => ({ ...result, similarity_score: Number(result?.similarity_score) }))
    .filter(result => result && result.knowledge_id != null && Number.isFinite(result.similarity_score))
    .filter(result => String(result.knowledge_id) !== selectedKey)
    .sort((left, right) => right.similarity_score - left.similarity_score)
    .filter(result => {
      const key = String(result.knowledge_id);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, Math.max(0, Math.min(MAX_SIMILAR_LIMIT, Math.trunc(Number(limit) || DEFAULT_SIMILAR_LIMIT))));
}

export async function fetchSimilarKnowledge(knowledgeId, options = {}) {
  const requestedLimit = Math.max(1, Math.min(
    MAX_SIMILAR_LIMIT,
    Math.trunc(Number(options.k) || DEFAULT_SIMILAR_LIMIT)
  ));
  const params = new URLSearchParams({
    k: String(requestedLimit),
    scope: "book"
  });
  const payload = await demoFetch(`/api/demo/knowledge/${knowledgeId}/similar?${params}`, {
    signal: options.signal
  });
  return { results: normalizeSimilarResults(payload.results, knowledgeId, requestedLimit) };
}

export function isUnavailable(reason) {
  return reason instanceof DemoApiError && [404, 405, 501, 503].includes(reason.status);
}
