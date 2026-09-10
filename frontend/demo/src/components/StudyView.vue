<script setup>
import { computed, inject, watch } from "vue";
import SectionAtlas from "./SectionAtlas.vue";
import KnowledgeViewer from "./KnowledgeViewer.vue";
import ImagePanel from "./ImagePanel.vue";
import NotePanel from "./NotePanel.vue";
import SearchPanel from "./SearchPanel.vue";

const props = defineProps({
  t: Object, book: Object, nodes: Array, sections:Array, canBack:Boolean, selectedId: Number,
  selectedNode: Object,
  mode: String, sideMode: String, notes: Array, similarResults: Array, similarStatus: String,
  similarError: String, discoveryKind: String, originBookId: Number, activeImage: Object,
  graph: Object, graphStatus: String, graphError: String
});
const emit = defineEmits(["continue", "back-object", "select", "retry-graph", "expand-graph", "soon", "action", "close-side", "save-note", "notes-page", "open-result", "return-origin", "move", "done", "open-image"]);
const current = computed(() => props.selectedNode
  || props.nodes.find(node => node.knowledge_id === props.selectedId)
  || props.nodes[0]);
const exercises = computed(() => props.nodes.filter(node => node.type === "exercise"));
const position = computed(() => exercises.value.findIndex(node => node.knowledge_id === current.value?.knowledge_id));
const closableSideModes = new Set(["notes", "similar", "image"]);
let sideTrigger = null;
const actionFocus = inject("actionFocus", () => null);
const actionBusy = inject("actionBusy", { value: false });
let restoreTrigger = null;

watch([() => props.sideMode, () => actionBusy.value], ([next, busy], [previous]) => {
  if (closableSideModes.has(next) && next !== previous) sideTrigger = actionFocus() || document.activeElement;
  if (next === "graph" && closableSideModes.has(previous)) {
    restoreTrigger = sideTrigger;
    sideTrigger = null;
  }
  if (!busy && restoreTrigger) {
    if (restoreTrigger.isConnected) restoreTrigger.focus();
    restoreTrigger = null;
  }
}, { flush: "post" });

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
        <div class="study-actions"><button type="button" :disabled="!canBack" @click="$emit('back-object')">{{ t.back }}</button><button type="button" :disabled="!current" @click="$emit('continue')">{{ t.continue }}</button><button type="button" @click="$emit('action','crystallize')">{{ t.crystallization }}</button>
          <button type="button" @click="$emit('action', 'project')">↗ {{ t.project }}</button>
          <button type="button" :class="{ active: sideMode === 'notes' }" @click="$emit('action', 'notes')">✎ {{ t.notes }}</button>
          <button type="button" :class="{ active: sideMode === 'similar' }" @click="$emit('action', 'similar')">✦ {{ t.cluster }}</button>
          <button type="button" @click="$emit('action', mode === 'questions' ? 'book' : 'train')">{{ mode === 'questions' ? '▥' : '→' }} {{ mode === 'questions' ? t.book : t.train }}</button>
        </div>
      </div>

      <div class="study-side-panel">
        <NotePanel v-if="sideMode === 'notes'" :t="t" :node="current" :notes="notes" :grimoire-id="book.grimoire_id" @close="$emit('close-side')" @save="$emit('save-note', $event)" @notes-page="$emit('notes-page')" />
        <SearchPanel v-else-if="sideMode === 'similar'" :t="t" :results="similarResults" :kind="discoveryKind" :status="similarStatus" :error="similarError" @close="$emit('close-side')" @open="$emit('open-result', $event)" />
        <ImagePanel :t="t" v-else-if="sideMode === 'image'" :image="activeImage" :node="current" @close="$emit('close-side')" />
        <SectionAtlas v-else :t="t" :nodes="nodes" :sections="sections" :graph="graph" :selected-id="current?.knowledge_id" @select="$emit('select',$event)" />
        <div class="study-side-controls">
          <button v-if="current" type="button" :class="{ done: current.completed }" @click="$emit('done', current)">{{ current.completed ? '✓ ' + t.completed : '○ ' + t.markDone }}</button>
          <button v-if="originBookId && originBookId !== book.grimoire_id" type="button" @click="$emit('return-origin')">← {{ t.returnOrigin }}</button>
        </div>
      </div>
    </div>
  </section>
</template>
