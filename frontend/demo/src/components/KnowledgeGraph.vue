<script setup>
import { computed, nextTick, ref, watch } from "vue";
import {
  MAX_RENDERED_GRAPH_NODES,
  boundedNeighborhood,
  graphCanvasHeightForRanks,
  graphCanvasWidthForSideLanes,
  graphLayout,
  isBookOrderProjection,
  normalizeGraph
} from "../domain/graph";

const props = defineProps({
  graph: { type: Object, default: null },
  status: { type: String, default: "" },
  error: { type: [String, Error, Object], default: null },
  selectedId: { type: [Number, String], default: null }
});
const emit = defineEmits(["select", "retry", "expand"]);
const MIN_CANVAS_WIDTH = 1000;
const FOCUS_VERTICAL_ANCHOR = 0.72;
const graphViewport = ref(null);

const normalized = computed(() => normalizeGraph(
  props.graph || { nodes: [], edges: [], focus_knowledge_id: props.selectedId },
  props.selectedId
));
const focusId = computed(() => Number(props.selectedId) || normalized.value.focus_knowledge_id);
const view = computed(() => boundedNeighborhood(normalized.value, focusId.value, MAX_RENDERED_GRAPH_NODES));
const effectiveStatus = computed(() => {
  if (props.status) return props.status;
  return props.graph ? "ready" : "idle";
});
const errorMessage = computed(() => {
  if (typeof props.error === "string") return props.error;
  return props.error?.message || "Please try again.";
});
const provisionalPositions = computed(() => graphLayout(view.value.nodes, view.value.edges, MIN_CANVAS_WIDTH, 560));
const rankCount = computed(() => new Set([...provisionalPositions.value.values()].map(position => position.rank)).size);
const maxBackbonePerRank = computed(() => {
  const rankCounts = new Map();
  for (const position of provisionalPositions.value.values()) {
    if (position.lane === 0) rankCounts.set(position.rank, (rankCounts.get(position.rank) || 0) + 1);
  }
  return Math.max(1, ...rankCounts.values());
});
const maxSideLane = computed(() => Math.max(0, ...[...provisionalPositions.value.values()].map(position => Math.abs(position.lane || 0))));
const canvasWidth = computed(() => graphCanvasWidthForSideLanes(maxSideLane.value, MIN_CANVAS_WIDTH));
const canvasHeight = computed(() => graphCanvasHeightForRanks(rankCount.value, maxBackbonePerRank.value));
const positions = computed(() => graphLayout(view.value.nodes, view.value.edges, canvasWidth.value, canvasHeight.value));

async function revealFocus() {
  if (effectiveStatus.value !== "ready") return;
  await nextTick();
  const viewport = graphViewport.value;
  const focusPosition = positions.value.get(focusId.value);
  if (!viewport || !focusPosition || !viewport.clientWidth || !viewport.clientHeight) return;

  const desiredTop = focusPosition.y - viewport.clientHeight * FOCUS_VERTICAL_ANCHOR;
  const desiredLeft = focusPosition.x - viewport.clientWidth / 2;
  viewport.scrollTop = Math.max(0, Math.min(viewport.scrollHeight - viewport.clientHeight, desiredTop));
  viewport.scrollLeft = Math.max(0, Math.min(viewport.scrollWidth - viewport.clientWidth, desiredLeft));
}

watch(
  [effectiveStatus, focusId, view, canvasWidth, canvasHeight],
  revealFocus,
  { immediate: true, flush: "post" }
);

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

function edgeKey(edge) {
  return `${edge.source_knowledge_id}:${edge.target_knowledge_id}:${edge.relation_type}`;
}

function edgePath(edge) {
  const source = positions.value.get(edge.source_knowledge_id);
  const target = positions.value.get(edge.target_knowledge_id);
  if (!source || !target) return "";
  const sourceY = source.y - 34;
  const targetY = target.y + 34;
  const middleY = (sourceY + targetY) / 2;
  return `M ${source.x} ${sourceY} C ${source.x} ${middleY}, ${target.x} ${middleY}, ${target.x} ${targetY}`;
}

function edgeLabel(edge) {
  return isBookOrderProjection(edge.relation_type) ? "Learning sequence" : edge.relation_type;
}

function requestExpansion(node, direction) {
  emit("expand", { knowledgeId: node.knowledge_id, direction });
}
</script>

<template>
  <section class="graph-shell semantic-graph-shell" :aria-busy="effectiveStatus === 'loading'">
    <header class="semantic-graph-header">
      <div>
        <p>Learning map</p>
        <h2 v-if="view.nodes.length">
          {{ view.nodes.length }} nearby {{ view.nodes.length === 1 ? 'idea' : 'ideas' }}
          <span>· {{ view.edges.length }} recorded {{ view.edges.length === 1 ? 'link' : 'links' }}</span>
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
      <div><strong>Mapping nearby ideas…</strong><p>Finding the prerequisites and supporting material around this item.</p></div>
    </div>
    <div v-else-if="effectiveStatus === 'unavailable'" class="graph-state" role="status">
      <span aria-hidden="true">◇</span>
      <div><strong>Learning map unavailable</strong><p>This item can still be read, but its learning links are not available yet.</p></div>
    </div>
    <div v-else-if="effectiveStatus === 'error'" class="graph-state graph-state-error" role="alert">
      <span aria-hidden="true">!</span>
      <div><strong>We couldn’t load the learning map.</strong><p>{{ errorMessage }}</p><button type="button" @click="emit('retry')">Try again</button></div>
    </div>
    <div v-else-if="effectiveStatus === 'idle'" class="graph-state" role="status">
      <span aria-hidden="true">◎</span>
      <div><strong>Choose an idea to begin.</strong><p>Its focused learning map will appear here.</p></div>
    </div>
    <div v-else-if="!view.nodes.length" class="graph-state" role="status">
      <span aria-hidden="true">◇</span>
      <div><strong>No nearby ideas found.</strong><p>There are no nearby ideas to show for this focus.</p></div>
    </div>

    <template v-else>
      <p v-if="!view.edges.length" class="edge-empty-state" role="status">
        No prerequisite, support, or learning-sequence links are available for this item yet. No connections have been guessed.
      </p>
      <p v-if="view.hiddenCount" class="graph-boundary-note">
        {{ view.hiddenCount }} other {{ view.hiddenCount === 1 ? 'idea is' : 'ideas are' }} outside this focused view. Choose a visible idea to refocus.
      </p>
      <div ref="graphViewport" class="graph-viewport" tabindex="0" aria-label="Scrollable learning map">
        <div class="semantic-canvas" :style="{ width: `${canvasWidth}px`, height: `${canvasHeight}px` }">
          <svg class="semantic-edges" :viewBox="`0 0 ${canvasWidth} ${canvasHeight}`" aria-hidden="true">
            <defs>
              <marker id="learning-map-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            </defs>
            <path
              v-for="edge in view.edges"
              :key="edgeKey(edge)"
              :d="edgePath(edge)"
              class="semantic-edge"
              :class="{ 'projection-edge': isBookOrderProjection(edge.relation_type) }"
              marker-end="url(#learning-map-arrow)"
            >
              <title>{{ edgeLabel(edge) }}</title>
            </path>
          </svg>

          <article
            v-for="node in view.nodes"
            :key="node.knowledge_id"
            class="semantic-node"
            :class="[`role-${node.graph_role}`, { selected: node.knowledge_id === focusId, done: node.completed }]"
            :style="{
              left: `${positions.get(node.knowledge_id)?.x - 86}px`,
              top: `${positions.get(node.knowledge_id)?.y - 34}px`
            }"
          >
            <button
              type="button"
              class="semantic-node-select"
              :aria-current="node.knowledge_id === focusId ? 'location' : undefined"
              :title="node.label"
              @click="emit('select', node.knowledge_id)"
            >
              <span>{{ roleLabel(node.graph_role) }}</span>
              <strong>{{ shortLabel(node.label) }}</strong>
              <small>{{ typeLabel(node.type) }}<template v-if="node.completed"> · completed</template></small>
            </button>
            <div v-if="node.collapsed_ancestor_count || node.collapsed_descendant_count" class="semantic-expanders">
              <button
                v-if="node.collapsed_ancestor_count"
                type="button"
                @click="requestExpansion(node, 'ancestors')"
              >+{{ node.collapsed_ancestor_count }} prerequisite{{ node.collapsed_ancestor_count === 1 ? '' : 's' }}</button>
              <button
                v-if="node.collapsed_descendant_count"
                type="button"
                @click="requestExpansion(node, 'descendants')"
              >+{{ node.collapsed_descendant_count }} next</button>
            </div>
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
  min-width: 100%;
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
  stroke-width: 2;
}

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

@keyframes graph-spin { to { transform: rotate(360deg); } }

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
