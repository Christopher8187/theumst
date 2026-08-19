<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({ nodes: Array, relationCounts: Object, selectedId: Number, t: Object });
const emit = defineEmits(["select"]);

const PAGE_SIZE = 71;
const MAIN_TYPES = new Set([
  "definition", "notation", "theorem", "lemma", "proposition", "corollary",
  "exercise", "just a statement", "jas"
]);
const preferredBranches = ["context", "example", "explanation", "remark", "claim"];
const windowStart = ref(0);

const selectedIndex = computed(() => Math.max(0, props.nodes.findIndex(node => node.knowledge_id === props.selectedId)));
const maxStart = computed(() => Math.max(0, props.nodes.length - PAGE_SIZE));

watch(selectedIndex, index => {
  if (index < windowStart.value + 8 || index >= windowStart.value + PAGE_SIZE - 8) {
    windowStart.value = Math.max(0, Math.min(maxStart.value, index - Math.floor(PAGE_SIZE / 2)));
  }
}, { immediate: true });

const visibleNodes = computed(() => props.nodes.slice(windowStart.value, windowStart.value + PAGE_SIZE));
const branchNames = computed(() => {
  const found = [...new Set(props.nodes.map(node => String(node.type || "other")))]
    .filter(type => !MAIN_TYPES.has(type));
  const ordered = preferredBranches.filter(type => found.includes(type));
  const remaining = found.filter(type => !ordered.includes(type));
  return [...ordered, ...remaining].slice(0, 6);
});
const lanes = computed(() => ["book/main", ...branchNames.value, ...(branchNames.value.length < new Set(
  props.nodes.filter(node => !MAIN_TYPES.has(String(node.type || "other"))).map(node => String(node.type || "other"))
).size ? ["other"] : [])]);

function laneFor(node) {
  const type = String(node.type || "other");
  if (MAIN_TYPES.has(type)) return 0;
  const branch = branchNames.value.indexOf(type);
  return branch >= 0 ? branch + 1 : lanes.value.length - 1;
}

function moveWindow(delta) {
  windowStart.value = Math.max(0, Math.min(maxStart.value, windowStart.value + delta));
}

function orderLabel(node, absoluteIndex) {
  const order = Array.isArray(node.source_order) ? node.source_order.join(".") : "";
  return order || String(absoluteIndex + 1).padStart(4, "0");
}
</script>

<template>
  <section class="graph-shell git-graph-shell">
    <header class="git-graph-header">
      <div>
        <p>Knowledge history</p>
        <h2>{{ nodes.length.toLocaleString() }} book objects</h2>
      </div>
      <div class="git-window-controls">
        <button type="button" :disabled="windowStart === 0" @click="moveWindow(-PAGE_SIZE)">↑ Earlier</button>
        <button type="button" :disabled="windowStart >= maxStart" @click="moveWindow(PAGE_SIZE)">Later ↓</button>
      </div>
    </header>

    <div class="git-lane-head" :style="{ '--lane-count': lanes.length }">
      <span v-for="(lane, index) in lanes" :key="lane" :class="{ main: index === 0 }">{{ lane }}</span>
    </div>

    <div class="git-log" :style="{ '--lane-count': lanes.length }">
      <button
        v-for="(node, localIndex) in visibleNodes"
        :key="node.knowledge_id"
        type="button"
        class="git-commit"
        :class="[node.type, { selected: node.knowledge_id === selectedId, done: node.completed }]"
        :style="{ '--commit-lane': laneFor(node) }"
        @click="emit('select', node.knowledge_id)"
      >
        <span class="git-tracks" aria-hidden="true">
          <i v-for="(_, laneIndex) in lanes" :key="laneIndex" class="git-rail" :style="{ '--rail': laneIndex }"></i>
          <i v-if="laneFor(node)" class="git-connector"></i>
          <i class="git-dot">{{ node.completed ? '✓' : '' }}</i>
        </span>
        <span class="git-order">{{ orderLabel(node, windowStart + localIndex) }}</span>
        <span class="git-copy">
          <strong>{{ node.label || node.type }}</strong>
          <small>{{ node.type }}<template v-if="relationCounts?.[node.knowledge_id]"> · {{ relationCounts[node.knowledge_id] }} links</template></small>
        </span>
        <span v-if="node.images?.length" class="git-image-count">▧ {{ node.images.length }}</span>
      </button>
    </div>

    <footer class="git-graph-footer">
      Showing {{ windowStart + 1 }}–{{ Math.min(nodes.length, windowStart + PAGE_SIZE) }} of {{ nodes.length }}
    </footer>
  </section>
</template>
