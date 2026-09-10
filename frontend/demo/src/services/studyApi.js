import { demoFetch, DemoApiError } from "../api";
import { normalizeGraph } from "../domain/graph";

const DEFAULT_SIMILAR_LIMIT = 10;
const MAX_SIMILAR_LIMIT = 25;

export async function fetchGraphSlice(grimoireId, focusId, options = {}) {
  const params = new URLSearchParams({
    focus: String(focusId),
    view: "atlas",
    ancestor_depth: String(options.ancestorDepth ?? 2),
    descendant_depth: String(options.descendantDepth ?? 2),
    include: "support,assessment",
    limit: "150"
  });
  const payload = await demoFetch(`/api/demo/grimoires/${grimoireId}/graph?${params}`, {
    signal: options.signal
  });
  return normalizeGraph(payload, focusId);
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
    scope: "available_books"
  });
  const payload = await demoFetch(`/api/demo/knowledge/${knowledgeId}/neighbors?${params}`, {
    signal: options.signal
  });
  if (!payload || !Array.isArray(payload.results)) {
    throw new DemoApiError("Malformed neighbor response", 502);
  }
  return { ...payload, results: normalizeSimilarResults(payload.results, knowledgeId, requestedLimit) };
}

export function isUnavailable(reason) {
  return reason instanceof DemoApiError && [404, 405, 501, 503].includes(reason.status);
}
