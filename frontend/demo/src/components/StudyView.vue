<script setup>
import { computed } from "vue";
import KnowledgeGraph from "./KnowledgeGraph.vue";
import KnowledgeViewer from "./KnowledgeViewer.vue";
import ImagePanel from "./ImagePanel.vue";
import NotePanel from "./NotePanel.vue";
import SearchPanel from "./SearchPanel.vue";

const props = defineProps({
  t: Object, book: Object, nodes: Array, relationCounts: Object, selectedId: Number,
  selectedNode: Object,
  mode: String, sideMode: String, notes: Array, searchResults: Array, searchLoading: Boolean,
  originBookId: Number, activeImage: Object
});
const emit = defineEmits(["select", "soon", "action", "close-side", "save-note", "notes-page", "open-result", "return-origin", "move", "done", "open-image"]);
const current = computed(() => props.selectedNode
  || props.nodes.find(node => node.knowledge_id === props.selectedId)
  || props.nodes[0]);
const exercises = computed(() => props.nodes.filter(node => node.type === "exercise"));
const position = computed(() => exercises.value.findIndex(node => node.knowledge_id === current.value?.knowledge_id));
</script>

<template>
  <section class="study-view">
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
          <button type="button" :class="{ active: sideMode === 'search' }" @click="$emit('action', 'crystallize')">✦ {{ t.crystallize }}</button>
          <button type="button" @click="$emit('action', mode === 'questions' ? 'book' : 'train')">{{ mode === 'questions' ? '▥' : '→' }} {{ mode === 'questions' ? t.book : t.train }}</button>
        </div>
      </div>

      <div class="study-side-panel">
        <NotePanel v-if="sideMode === 'notes'" :t="t" :node="current" :notes="notes" :grimoire-id="book.grimoire_id" @close="$emit('close-side')" @save="$emit('save-note', $event)" @notes-page="$emit('notes-page')" />
        <SearchPanel v-else-if="sideMode === 'search'" :t="t" :results="searchResults" :loading="searchLoading" @close="$emit('close-side')" @open="$emit('open-result', $event)" />
        <ImagePanel v-else-if="sideMode === 'image'" :image="activeImage" :node="current" @close="$emit('close-side')" />
        <KnowledgeGraph v-else :t="t" :nodes="nodes" :relation-counts="relationCounts" :selected-id="current?.knowledge_id" @select="$emit('select', $event)" />
        <div class="study-side-controls">
          <button v-if="current" type="button" :class="{ done: current.completed }" @click="$emit('done', current)">{{ current.completed ? '✓ ' + t.completed : '○ ' + t.markDone }}</button>
          <button v-if="originBookId && originBookId !== book.grimoire_id" type="button" @click="$emit('return-origin')">← {{ t.returnOrigin }}</button>
        </div>
      </div>
    </div>
  </section>
</template>
