<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { buildAtlas } from "../domain/atlas";
import { renderMath } from "../math";

const props = defineProps({
  t: Object,
  nodes: Array,
  sections: Array,
  graph: Object,
  selectedId: [Number, String],
});
const emit = defineEmits(["select"]);
const bookDistance = ref(3),
  dependencyDistance = ref(2),
  view = ref("reading"),
  scale = ref(0.65);
const viewport = ref(null);
const reportedGap = ref(null);
const gapReport = computed(() =>
  reportedGap.value
    ? props.t.omittedPositions
        .replace("{start}", reportedGap.value.a + 1)
        .replace("{end}", reportedGap.value.b - 1)
    : "",
);
function reportGap(gap) {
  reportedGap.value = gap;
}
watch(
  () => props.selectedId,
  () => {
    reportedGap.value = null;
  },
);
const relations = computed(() =>
  props.graph?.authored_dependencies === true
    ? (props.graph.edges || []).filter((edge) => edge.relation_type === "dependency")
    : [],
);
const layout = computed(() =>
  buildAtlas(
    props.nodes || [],
    props.sections || [],
    relations.value,
    props.selectedId,
    {
      book: bookDistance.value,
      dependency: dependencyDistance.value,
      view: view.value,
    },
  ),
);
const path = (edge) =>
  edge.points.map((p, i) => `${i ? "L" : "M"} ${p.x} ${p.y}`).join(" ");
const label = (edge) =>
  edge.type === "dependency" ? props.t.dependency : props.t.readingOrder;
async function center() {
  await nextTick();
  const node = layout.value.placed.find(
    (n) => String(n.knowledge_id) === String(props.selectedId),
  );
  if (!node || !viewport.value) return;
  viewport.value.scrollLeft = Math.max(
    0,
    (node.x + 80) * scale.value - viewport.value.clientWidth / 2,
  );
  viewport.value.scrollTop = Math.max(
    0,
    (node.y + 32) * scale.value - viewport.value.clientHeight / 2,
  );
}
watch([layout, scale], center, { flush: "post" });
</script>

<template>
  <section class="section-atlas" :aria-label="t.atlas">
    <header>
      <h2>{{ t.atlas }}</h2>
      <button type="button" @click="center">{{ t.centerCurrent }}</button>
    </header>
    <div class="atlas-controls">
      <label
        >{{ t.bookDistance }} {{ bookDistance
        }}<input
          v-model.number="bookDistance"
          type="range"
          min="0"
          max="24"
          :aria-label="t.bookDistance"
      /></label>
      <label
        >{{ t.dependencyDistance }} {{ dependencyDistance
        }}<input
          v-model.number="dependencyDistance"
          type="range"
          min="0"
          max="8"
          :aria-label="t.dependencyDistance"
      /></label>
      <div class="atlas-views">
        <button
          type="button"
          :aria-pressed="view === 'reading'"
          @click="view = 'reading'"
        >
          {{ t.readingRows }}</button
        ><button
          type="button"
          :aria-pressed="view === 'hierarchy'"
          @click="view = 'hierarchy'"
        >
          {{ t.hierarchy }}
        </button>
      </div>
      <p>{{ t.eitherDistance }}</p>
    </div>
    <div class="atlas-legend">
      <span class="gold">{{ t.readingOrder }}</span
      ><span>{{ t.dependency }}</span>
    </div>
    <p v-if="!relations.length" class="atlas-message">
      {{ t.noAuthoredDependencies }}
    </p>
    <div
      ref="viewport"
      class="atlas-viewport"
      tabindex="0"
      :aria-label="t.atlas"
    >
      <svg
        :width="layout.width * scale"
        :height="layout.height * scale"
        :viewBox="`0 0 ${layout.width} ${layout.height}`"
        role="group"
        :aria-label="t.atlas"
      >
        <defs>
          <marker
            id="atlas-gold"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L7,3 L0,6" fill="#e4c66c" />
          </marker>
          <marker
            id="atlas-dependency"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L7,3 L0,6" fill="#9eb5d8" />
          </marker>
        </defs>
        <g v-for="p in layout.parents" :key="p.id" class="atlas-parent">
          <rect
            :x="p.x"
            :y="p.y"
            :width="p.w"
            :height="p.h"
            :rx="p.depth === 0 ? 44 : 24"
          />
          <text :x="p.x + 30" :y="p.y + 39">
            {{ layout.hierarchy[p.id].name }}
          </text>
        </g>
        <g v-for="s in layout.tiles" :key="s.id" class="atlas-section">
          <rect :x="s.x" :y="s.y" :width="s.w" :height="s.h" rx="28" />
          <text :x="s.x + 16" :y="s.y + 29">
            {{ layout.hierarchy[s.id].name.slice(0, 27) }}
            <title>{{ layout.hierarchy[s.id].name }}</title>
          </text>
          <text :x="s.x + 16" :y="s.y + 48">
            {{ s.members.length }} {{ t.objectsShown }}
          </text>
        </g>
        <path
          v-for="e in layout.edges"
          :key="`${e.type}-${e.a}-${e.b}`"
          :d="path(e)"
          class="atlas-edge"
          :class="e.type"
          :marker-end="
            e.type === 'dependency'
              ? 'url(#atlas-dependency)'
              : 'url(#atlas-gold)'
          "
        >
          <title>{{ label(e) }}</title>
        </path>
        <g
          v-for="b in layout.badges"
          :key="`${b.a}-${b.b}`"
          class="atlas-gap"
          role="button"
          tabindex="0"
          :aria-label="`+${b.count} ${t.outsideView}`"
          @click="reportGap(b)"
          @keydown.enter.prevent="reportGap(b)"
          @keydown.space.prevent="reportGap(b)"
        >
          <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" rx="6" />
          <text :x="b.x + b.w / 2" :y="b.y + 16" text-anchor="middle">
            +{{ b.count }} {{ t.outsideView }}
          </text>
        </g>
        <foreignObject
          v-for="n in layout.placed"
          :key="n.knowledge_id"
          :x="n.x"
          :y="n.y"
          width="160"
          height="64"
          ><button
            xmlns="http://www.w3.org/1999/xhtml"
            type="button"
            class="atlas-node"
            :class="{
              selected: String(n.knowledge_id) === String(selectedId),
              done: n.completed,
            }"
            :aria-label="n.title"
            @click="emit('select', n.knowledge_id)"
          >
            <span class="atlas-node-title" v-html="renderMath(n.title)"></span
            ><small>{{ n.completed ? "✓ " : "" }}{{ n.id }}</small>
          </button></foreignObject
        >
      </svg>
    </div>
    <p v-if="reportedGap" role="status" class="atlas-message">
      {{ gapReport }}
    </p>
    <footer>
      <span
        >{{ layout.placed.length }} / {{ layout.candidates }}
        {{ t.qualifyingObjects }}</span
      ><label
        >{{ t.scale
        }}<select v-model.number="scale">
          <option :value="0.5">50%</option>
          <option :value="0.65">65%</option>
          <option :value="0.8">80%</option>
          <option :value="1">100%</option>
        </select></label
      >
    </footer>
    <p v-if="graph?.truncated || layout.omitted || layout.unlabelled" role="status">
      {{ t.limitedArrows }}
    </p>
  </section>
</template>

<style scoped>
.section-atlas {
  background: #151b27;
  border: 1px solid #455169;
  border-radius: 12px;
  overflow: hidden;
  color: #e1e6ef;
}
.section-atlas header,
.section-atlas footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 8px;
}
.section-atlas h2 {
  font-size: 18px;
  margin: 0;
}
.section-atlas button,
.section-atlas select {
  font: inherit;
  background: #263247;
  color: inherit;
  border: 1px solid #62718a;
  border-radius: 5px;
  padding: 6px 10px;
}
.atlas-controls {
  padding: 0 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.atlas-controls label {
  display: grid;
  gap: 5px;
  font-size: 12px;
}
.atlas-controls p {
  font-size: 12px;
  margin: 0;
}
.atlas-views {
  display: flex;
  gap: 6px;
}
.atlas-views button[aria-pressed="true"] {
  border-color: #e4c66c;
  color: #e4c66c;
}
.atlas-viewport {
  contain: layout paint;
  height: 580px;
  overflow: auto;
  overscroll-behavior: contain;
}
.atlas-legend {
  display: flex;
  gap: 20px;
  padding: 10px 16px;
  font-size: 12px;
  color: #9eb5d8;
}
.gold {
  color: #e4c66c;
}
.atlas-message {
  padding: 0 16px;
  font-size: 12px;
  color: #b8c1cf;
}
.atlas-parent rect {
  fill: #8e9ec808;
  stroke: #8e9ec8;
  stroke-width: 2;
}
.atlas-parent text {
  fill: #d0daf0;
  font-size: 18px;
}
.atlas-section rect {
  fill: #9fafdf18;
}
.atlas-section text {
  fill: #c9d2e8;
  font-size: 12px;
}
.atlas-edge {
  fill: none;
  stroke: #9eb5d8;
  stroke-width: 2;
}
.atlas-edge.order,
.atlas-edge.gap {
  stroke: #e4c66c;
}
.atlas-edge.gap {
  stroke-dasharray: 5 5;
}
.atlas-gap {
  cursor: pointer;
}
.atlas-gap:focus-visible rect {
  stroke-width: 3;
}
.atlas-gap rect {
  fill: #1b2433;
  stroke: #e4c66c;
}
.atlas-gap text {
  fill: #f3d778;
  font-size: 11px;
}
.atlas-node {
  width: 160px;
  height: 64px;
  display: flex;
  gap: 3px;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  overflow: hidden;
}
.atlas-node-title {
  font-size: 12px;
  max-height: 52px;
  overflow: hidden;
}
.atlas-node.selected {
  border: 2px solid #f0d37e;
  background: #354055;
}
.atlas-node.done small {
  color: #8ed2ab;
}
.section-atlas button:focus-visible,
.atlas-viewport:focus-visible {
  outline: 3px solid #f0d37e;
  outline-offset: 2px;
}
.section-atlas footer {
  font-size: 12px;
}
.section-atlas footer label {
  display: flex;
  gap: 6px;
  align-items: center;
}
@media (max-width: 600px) {
  .atlas-controls {
    grid-template-columns: 1fr;
  }
  .atlas-viewport {
    height: 420px;
  }
}
</style>
