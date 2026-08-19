<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  hasProjectionChunk,
  isBookOrderProjection,
  mergeProjectionChunks,
  normalizeProjectionManifest,
  projectionChunkAtScroll,
  projectionChunkIndexForKnowledge,
  projectionChunkWindow,
  projectionScrollTopForKnowledge
} from "../domain/graph";

const props = defineProps({
  projection: { type: Object, default: null },
  status: { type: String, default: "" },
  error: { type: [String, Error, Object], default: null },
  selectedId: { type: [Number, String], default: null }
});
const emit = defineEmits(["select", "request-chunk"]);
const FOCUS_VERTICAL_ANCHOR = 0.72;
const graphViewport = ref(null);
const activeChunkIndex = ref(0);
const requestedChunks = new Set();

const manifest = computed(() => normalizeProjectionManifest(props.projection || {}));
const revisionKey = computed(() => [
  manifest.value.projection_revision || "no-projection-revision",
  manifest.value.book_revision || "no-book-revision"
].join(":"));
const mountedChunkIndices = computed(() => projectionChunkWindow(activeChunkIndex.value, manifest.value, 1));
const view = computed(() => mergeProjectionChunks(props.projection || {}, mountedChunkIndices.value));
const effectiveStatus = computed(() => {
  if (props.status) return props.status;
  if (props.projection?.status) return props.projection.status;
  return manifest.value.total_nodes ? "ready" : (props.projection ? "unavailable" : "idle");
});
const errorMessage = computed(() => {
  const error = props.error ?? props.projection?.error;
  if (typeof error === "string") return error;
  return error?.message || "Please try again.";
});
const selectedNumericId = computed(() => Number(props.selectedId) || null);
const nodeById = computed(() => new Map(view.value.nodes.map(node => [node.knowledge_id, node])));
const loadedChunkCount = computed(() => mountedChunkIndices.value.filter(index => (
  hasProjectionChunk(props.projection, index)
)).length);

function requestChunk(index) {
  if (!Number.isInteger(index) || index < 0 || index >= manifest.value.chunk_count) return;
  if (hasProjectionChunk(props.projection, index)) return;
  const key = `${revisionKey.value}:${index}`;
  if (requestedChunks.has(key)) return;
  requestedChunks.add(key);
  emit("request-chunk", index);
}

function requestVisibleWindow() {
  for (const index of mountedChunkIndices.value) requestChunk(index);
}

async function scrollToKnowledge(knowledgeId) {
  const chunkIndex = projectionChunkIndexForKnowledge(manifest.value, knowledgeId);
  if (chunkIndex == null || !hasProjectionChunk(props.projection, chunkIndex)) return false;
  activeChunkIndex.value = chunkIndex;
  await nextTick();
  const viewport = graphViewport.value;
  if (!viewport) return false;
  const scrollTop = projectionScrollTopForKnowledge(
    manifest.value,
    knowledgeId,
    viewport.clientHeight,
    FOCUS_VERTICAL_ANCHOR
  );
  if (scrollTop == null) return false;
  viewport.scrollTop = scrollTop;
  viewport.scrollLeft = Math.max(0, manifest.value.center_x - viewport.clientWidth / 2);
  return true;
}

function onViewportScroll() {
  const viewport = graphViewport.value;
  if (!viewport) return;
  const nextChunk = projectionChunkAtScroll(manifest.value, viewport.scrollTop, viewport.clientHeight);
  if (nextChunk == null || nextChunk === activeChunkIndex.value) return;
  activeChunkIndex.value = nextChunk;
  requestVisibleWindow();
}

watch(revisionKey, async () => {
  requestedChunks.clear();
  const selectedChunk = projectionChunkIndexForKnowledge(manifest.value, selectedNumericId.value);
  activeChunkIndex.value = selectedChunk ?? manifest.value.initial_chunk;
  requestVisibleWindow();
  if (selectedNumericId.value != null && hasProjectionChunk(props.projection, activeChunkIndex.value)) {
    await scrollToKnowledge(selectedNumericId.value);
  }
}, { immediate: true, flush: "post" });

watch(selectedNumericId, async selectedId => {
  if (selectedId == null) return;
  const chunkIndex = projectionChunkIndexForKnowledge(manifest.value, selectedId);
  if (chunkIndex == null) return;
  if (!hasProjectionChunk(props.projection, chunkIndex)) {
    requestChunk(chunkIndex);
    return;
  }
  await scrollToKnowledge(selectedId);
}, { flush: "post" });

watch(
  () => props.projection?.chunks,
  async () => {
    for (const index of mountedChunkIndices.value) {
      if (hasProjectionChunk(props.projection, index)) requestedChunks.delete(`${revisionKey.value}:${index}`);
    }
    const selectedId = selectedNumericId.value;
    if (selectedId == null) return;
    const selectedChunk = projectionChunkIndexForKnowledge(manifest.value, selectedId);
    if (selectedChunk != null && selectedChunk !== activeChunkIndex.value && hasProjectionChunk(props.projection, selectedChunk)) {
      await scrollToKnowledge(selectedId);
      return;
    }
    if (selectedChunk === activeChunkIndex.value && hasProjectionChunk(props.projection, selectedChunk)) {
      await scrollToKnowledge(selectedId);
    }
  },
  { flush: "post" }
);

onMounted(async () => {
  await nextTick();
  requestVisibleWindow();
  if (selectedNumericId.value != null) await scrollToKnowledge(selectedNumericId.value);
});

function roleLabel(role) {
  return ({
    backbone: "Main idea",
    support: "Supports",
    assessment: "Practice",
    fragment: "Related idea",
    crosslink: "Related idea",
    unclassified: "Idea"
  })[role] || "Idea";
}

function typeLabel(type) {
  const value = String(type || "idea");
  return value === "jas" || value === "just a statement" ? "statement" : value;
}

function shortLabel(label) {
  const text = String(label || "Untitled idea").trim();
  return text.length > 58 ? `${text.slice(0, 55)}…` : text;
}

function edgePath(edge) {
  const source = nodeById.value.get(edge.source_knowledge_id)?.position;
  const target = nodeById.value.get(edge.target_knowledge_id)?.position;
  if (!source || !target) return "";
  const sourceY = source.y - 34;
  const targetY = target.y + 34;
  const middleY = (sourceY + targetY) / 2;
  return `M ${source.x} ${sourceY} C ${source.x} ${middleY}, ${target.x} ${middleY}, ${target.x} ${targetY}`;
}

function edgeLabel(edge) {
  return isBookOrderProjection(edge.relation_type) ? "Learning sequence" : edge.relation_type;
}

function isSpineEdge(edge) {
  return nodeById.value.get(edge.source_knowledge_id)?.graph_role === "backbone"
    && nodeById.value.get(edge.target_knowledge_id)?.graph_role === "backbone";
}

</script>

<template>
  <section class="graph-shell semantic-graph-shell" :aria-busy="effectiveStatus === 'loading'">
    <header class="semantic-graph-header">
      <div>
        <p>Learning map</p>
        <h2 v-if="view.nodes.length">
          {{ manifest.total_nodes }} book {{ manifest.total_nodes === 1 ? 'idea' : 'ideas' }}
          <span>· {{ view.nodes.length }} visible · {{ view.edges.length }} recorded {{ view.edges.length === 1 ? 'link' : 'links' }}</span>
        </h2>
        <h2 v-else>How this idea fits together</h2>
      </div>
      <div class="semantic-legend" aria-label="Learning map key">
        <span class="sequence-link">Learning sequence</span>
        <span class="role-backbone">Main idea</span>
        <span class="role-support">Supports</span>
        <span class="role-assessment">Practice</span>
        <span class="role-fragment">Related idea</span>
      </div>
    </header>

    <div v-if="effectiveStatus === 'loading'" class="graph-state" role="status">
      <span class="graph-state-spinner" aria-hidden="true"></span>
      <div><strong>Opening the learning map…</strong><p>Loading this part of the book.</p></div>
    </div>
    <div v-else-if="effectiveStatus === 'unavailable'" class="graph-state" role="status">
      <span aria-hidden="true">◇</span>
      <div><strong>Learning map unavailable</strong><p>This item can still be read, but its learning links are not available yet.</p></div>
    </div>
    <div v-else-if="effectiveStatus === 'error'" class="graph-state graph-state-error" role="alert">
      <span aria-hidden="true">!</span>
      <div><strong>We couldn’t load the learning map.</strong><p>{{ errorMessage }}</p></div>
    </div>
    <div v-else-if="effectiveStatus === 'idle'" class="graph-state" role="status">
      <span aria-hidden="true">◎</span>
      <div><strong>Choose an idea to begin.</strong><p>Its place in the book will appear here.</p></div>
    </div>
    <div v-else-if="!view.nodes.length" class="graph-state" role="status">
      <span aria-hidden="true">◇</span>
      <div><strong>This part of the map is still loading.</strong><p>The book structure is available, but no items in this section have arrived yet.</p></div>
    </div>

    <template v-else>
      <p v-if="!view.edges.length" class="edge-empty-state" role="status">
        No recorded learning-sequence links are available in these loaded sections. No connections have been guessed.
      </p>
      <p class="graph-boundary-note">
        Showing {{ loadedChunkCount }} of {{ mountedChunkIndices.length }} nearby {{ mountedChunkIndices.length === 1 ? 'section' : 'sections' }}. Scroll to continue through the book.
      </p>
      <div ref="graphViewport" class="graph-viewport" tabindex="0" aria-label="Scrollable learning map" @scroll.passive="onViewportScroll">
        <div class="semantic-canvas projection-spacer" :style="{ width: `${manifest.width}px`, height: `${manifest.total_height}px` }">
          <svg class="semantic-edges" :viewBox="`0 0 ${manifest.width} ${manifest.total_height}`" aria-hidden="true">
            <defs>
              <marker id="learning-map-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            </defs>
            <path
              v-for="edge in view.edges"
              :key="edge.edge_id"
              :d="edgePath(edge)"
              class="semantic-edge"
              :class="{
                'projection-edge': isBookOrderProjection(edge.relation_type),
                'spine-edge': isSpineEdge(edge)
              }"
              marker-end="url(#learning-map-arrow)"
            >
              <title>{{ edgeLabel(edge) }}</title>
            </path>
          </svg>

          <article
            v-for="node in view.nodes"
            :key="node.knowledge_id"
            class="semantic-node"
            :class="[`role-${node.graph_role}`, { selected: node.knowledge_id === selectedNumericId, done: node.completed }]"
            :style="{
              left: `${node.position.x - 86}px`,
              top: `${node.position.y - 34}px`
            }"
          >
            <button
              type="button"
              class="semantic-node-select"
              :aria-current="node.knowledge_id === selectedNumericId ? 'location' : undefined"
              :title="node.label"
              @click="emit('select', node.knowledge_id)"
            >
              <span>{{ roleLabel(node.graph_role) }}</span>
              <strong>{{ shortLabel(node.label) }}</strong>
              <small>{{ typeLabel(node.type) }}<template v-if="node.completed"> · completed</template></small>
            </button>
          </article>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.semantic-graph-shell {
  min-height: 360px;
  overflow: hidden;
  background: linear-gradient(155deg, #0b1724, #07111b);
}

.semantic-graph-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(174, 199, 215, 0.14);
}

.semantic-graph-header p,
.semantic-graph-header h2 {
  margin: 0;
}

.semantic-graph-header p {
  color: #70d8cf;
  font-size: 0.75rem;
  font-weight: 700;
}

.semantic-graph-header h2 {
  margin-top: 4px;
  color: #f4f0e7;
  font-size: 1.1rem;
}

.semantic-graph-header h2 span {
  color: #8fa5b5;
  font-size: 0.8rem;
  font-weight: 500;
}

.semantic-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.semantic-legend span {
  border: 1px solid rgba(174, 199, 215, 0.16);
  border-radius: 999px;
  padding: 5px 8px;
  color: #afbec9;
  font-size: 0.72rem;
}

.semantic-legend span::before {
  content: "";
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
  background: #88a3b4;
}

.semantic-legend .role-backbone::before { background: #70d8cf; }
.semantic-legend .role-support::before { background: #d9b56c; }
.semantic-legend .role-assessment::before { background: #a994db; }
.semantic-legend .role-fragment::before { background: #8fa5b5; }
.semantic-legend .sequence-link::before {
  width: 14px;
  height: 2px;
  border-radius: 0;
  background: #70d8cf;
}

.graph-state {
  min-height: 270px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 32px;
  color: #91a6b5;
  text-align: left;
}

.graph-state > span {
  color: #70d8cf;
  font-size: 1.6rem;
}

.graph-state strong {
  color: #f4f0e7;
}

.graph-state p {
  max-width: 34rem;
  margin: 5px 0 0;
}

.graph-state button,
.semantic-expanders button {
  border: 1px solid rgba(112, 216, 207, 0.35);
  border-radius: 8px;
  padding: 6px 9px;
  background: rgba(112, 216, 207, 0.08);
  color: #bfe7e2;
  cursor: pointer;
}

.graph-state button { margin-top: 12px; }

.graph-state-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid rgba(112, 216, 207, 0.2);
  border-top-color: #70d8cf;
  border-radius: 50%;
  animation: graph-spin 0.8s linear infinite;
}

.edge-empty-state,
.graph-boundary-note {
  margin: 0;
  padding: 10px 18px;
  border-bottom: 1px solid rgba(174, 199, 215, 0.12);
  color: #9fb0bd;
  font-size: 0.8rem;
}

.edge-empty-state { color: #d6c398; }

.graph-viewport {
  max-height: min(68vh, 720px);
  overflow: auto;
  outline: none;
  scrollbar-gutter: stable;
}

.graph-viewport:focus-visible {
  box-shadow: inset 0 0 0 3px rgba(112, 216, 207, 0.55);
}

.semantic-canvas {
  position: relative;
  min-width: 0;
}

.semantic-edges {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.semantic-edge {
  fill: none;
  stroke: rgba(143, 165, 181, 0.48);
  stroke-width: 1.5;
}

.semantic-edge.projection-edge {
  stroke: rgba(112, 216, 207, 0.72);
  stroke-width: 1.6;
}

.semantic-edge.spine-edge { stroke-width: 2.8; }

#learning-map-arrow path { fill: #829aa9; }

.semantic-node {
  position: absolute;
  z-index: 1;
  width: 172px;
  min-height: 68px;
  border: 1px solid rgba(143, 165, 181, 0.3);
  border-radius: 13px;
  background: #101f2d;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
}

.semantic-node.role-backbone { border-color: rgba(112, 216, 207, 0.55); }
.semantic-node.role-support { border-color: rgba(217, 181, 108, 0.48); }
.semantic-node.role-assessment { border-color: rgba(169, 148, 219, 0.5); }
.semantic-node.role-fragment,
.semantic-node.role-crosslink { border-style: dashed; }
.semantic-node.selected { box-shadow: 0 0 0 3px rgba(112, 216, 207, 0.22), 0 10px 24px rgba(0, 0, 0, 0.25); }

.semantic-node-select {
  width: 100%;
  border: 0;
  border-radius: inherit;
  padding: 9px 10px;
  background: transparent;
  color: #edf0ea;
  text-align: left;
  cursor: pointer;
}

.semantic-node-select span,
.semantic-node-select small {
  display: block;
  color: #8fa5b5;
  font-size: 0.67rem;
}

.semantic-node-select strong {
  display: block;
  margin: 3px 0;
  font-size: 0.78rem;
  line-height: 1.25;
}

.semantic-node-select:focus-visible,
.semantic-expanders button:focus-visible,
.graph-state button:focus-visible {
  outline: 3px solid rgba(112, 216, 207, 0.72);
  outline-offset: 3px;
}

.semantic-expanders {
  display: flex;
  gap: 4px;
  padding: 0 8px 8px;
}

.semantic-expanders button {
  flex: 1;
  padding: 4px;
  font-size: 0.62rem;
}

.semantic-fan-summary {
  flex: 1;
  color: #8fa5b5;
  font-size: 0.62rem;
  text-align: center;
}

@keyframes graph-spin { to { transform: rotate(360deg); } }

@media (min-width: 1200px) {
  .graph-viewport { overflow-x: hidden; }
}

@media (max-width: 700px) {
  .semantic-graph-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .semantic-legend { justify-content: flex-start; }
}

@media (prefers-reduced-motion: reduce) {
  .graph-state-spinner { animation: none; }
  .semantic-node,
  .semantic-node-select { transition: none !important; }
}
</style>
