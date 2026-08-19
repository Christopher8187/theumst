<script setup>
import { computed, nextTick, watch } from "vue";
import KnowledgeGraph from "./KnowledgeGraph.vue";
import KnowledgeViewer from "./KnowledgeViewer.vue";
import ImagePanel from "./ImagePanel.vue";
import NotePanel from "./NotePanel.vue";
import SearchPanel from "./SearchPanel.vue";

const props = defineProps({
  t: Object, book: Object, nodes: Array, selectedId: Number,
  selectedNode: Object,
  mode: String, sideMode: String, notes: Array, similarResults: Array, similarStatus: String,
  similarError: String, originBookId: Number, activeImage: Object,
  projection: Object, projectionStatus: String, projectionError: String
});
const emit = defineEmits(["select", "request-chunk", "retry", "soon", "action", "close-side", "save-note", "notes-page", "open-result", "return-origin", "move", "done", "open-image"]);
const current = computed(() => props.selectedNode
  || props.nodes.find(node => node.knowledge_id === props.selectedId)
  || props.nodes[0]);
const exercises = computed(() => props.nodes.filter(node => node.type === "exercise"));
const position = computed(() => exercises.value.findIndex(node => node.knowledge_id === current.value?.knowledge_id));
const closableSideModes = new Set(["notes", "similar", "image"]);
let sideTrigger = null;

watch(() => props.sideMode, (next, previous) => {
  if (closableSideModes.has(next) && next !== previous) sideTrigger = document.activeElement;
  if (next === "graph" && closableSideModes.has(previous)) {
    const trigger = sideTrigger;
    sideTrigger = null;
    nextTick(() => {
      if (trigger?.isConnected && typeof trigger.focus === "function") trigger.focus();
    });
  }
});

function closeSidePanel() {
  if (closableSideModes.has(props.sideMode)) emit("close-side");
}
</script>

<template>
  <section class="study-view" @keydown.esc.stop="closeSidePanel">
    <div class="study-topbar">
      <div><p>{{ mode === 'questions' ? t.questionMode : t.textMode }}</p><h1>{{ book?.title }}</h1></div>
      <div v-if="current?.breadcrumbs?.length" class="breadcrumbs">
        <span v-for="section in current.breadcrumbs" :key="section.section_id"><i>{{ section.number }}</i>{{ section.name }}</span>
      </div>
    </div>

    <div class="study-split">
      <div class="knowledge-side">
        <div v-if="mode === 'questions'" class="exercise-nav">
          <button :disabled="position <= 0" type="button" @click="$emit('move', -1)">← {{ t.previous }}</button>
          <span>{{ Math.max(position + 1, 1) }} / {{ exercises.length }}</span>
          <button :disabled="position >= exercises.length - 1" type="button" @click="$emit('move', 1)">{{ t.next }} →</button>
        </div>
        <KnowledgeViewer :t="t" :node="current" :mode="mode" @soon="$emit('soon', $event)" @open-image="$emit('open-image', $event)" />
        <div class="study-actions">
          <button type="button" @click="$emit('action', 'project')">↗ {{ t.project }}</button>
          <button type="button" :class="{ active: sideMode === 'notes' }" @click="$emit('action', 'notes')">✎ {{ t.notes }}</button>
          <button type="button" :class="{ active: sideMode === 'similar' }" @click="$emit('action', 'similar')">✦ {{ t.cluster }}</button>
          <button type="button" @click="$emit('action', mode === 'questions' ? 'book' : 'train')">{{ mode === 'questions' ? '▥' : '→' }} {{ mode === 'questions' ? t.book : t.train }}</button>
        </div>
      </div>

      <div class="study-side-panel">
        <NotePanel v-if="sideMode === 'notes'" :t="t" :node="current" :notes="notes" :grimoire-id="book.grimoire_id" @close="$emit('close-side')" @save="$emit('save-note', $event)" @notes-page="$emit('notes-page')" />
        <SearchPanel v-else-if="sideMode === 'similar'" :t="t" :results="similarResults" :status="similarStatus" :error="similarError" @close="$emit('close-side')" @open="$emit('open-result', $event)" />
        <ImagePanel v-else-if="sideMode === 'image'" :image="activeImage" :node="current" @close="$emit('close-side')" />
        <KnowledgeGraph v-else :t="t" :projection="projection" :status="projectionStatus" :error="projectionError" :selected-id="selectedId" @select="$emit('select', $event)" @request-chunk="$emit('request-chunk', $event)" @retry="$emit('retry')" />
        <div class="study-side-controls">
          <button v-if="current" type="button" :class="{ done: current.completed }" @click="$emit('done', current)">{{ current.completed ? '✓ ' + t.completed : '○ ' + t.markDone }}</button>
          <button v-if="originBookId && originBookId !== book.grimoire_id" type="button" @click="$emit('return-origin')">← {{ t.returnOrigin }}</button>
        </div>
      </div>
    </div>
  </section>
</template>
