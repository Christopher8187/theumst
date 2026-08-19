<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({ t: Object, notes: Array, grimoireId: Number });
const emit = defineEmits(["save", "delete"]);
const selectedId = ref(null);
const tag = ref("");
const content = ref("");

const selected = computed(() => props.notes.find(note => note.demo_note_id === selectedId.value));
const scribbles = computed(() => props.notes.filter(note => note.note_type === "scribble"));
const attached = computed(() => props.notes.filter(note => note.note_type === "attached"));

watch(() => props.notes, () => {
  if (selectedId.value && !selected.value) selectedId.value = null;
}, { deep: true });

function choose(note) {
  selectedId.value = note.demo_note_id;
  tag.value = note.tag;
  content.value = note.content;
}

function create() {
  selectedId.value = null;
  tag.value = "";
  content.value = "";
}

function save() {
  emit("save", {
    id: selected.value?.demo_note_id,
    grimoire_id: selected.value?.grimoire_id || props.grimoireId || null,
    knowledge_id: selected.value?.knowledge_id || null,
    note_type: selected.value?.note_type || "scribble",
    tag: tag.value,
    content: content.value
  });
}
</script>

<template>
  <section class="notes-desk">
    <div class="note-editor-pane">
      <header><div><p class="demo-kicker">{{ t.notesMode }}</p><h1>{{ selected?.knowledge_label || t.newScribble }}</h1></div><span v-if="selected?.knowledge_id">#{{ selected.knowledge_id }}</span></header>
      <label>{{ t.tag }}<input v-model="tag" placeholder="idea · question · proof"></label>
      <textarea v-model="content" :placeholder="t.notePlaceholder"></textarea>
      <div class="note-editor-actions">
        <button v-if="selected" type="button" class="danger-text" @click="$emit('delete', selected)">{{ t.delete }}</button>
        <button type="button" class="primary-button" @click="save">{{ t.saveNote }}</button>
      </div>
    </div>
    <div class="note-constellation-pane">
      <header><div><p class="demo-kicker">PERSONAL KNOWLEDGE LAYER</p><h2>{{ t.noteConstellation }}</h2></div><button type="button" class="ghost-button" @click="create">＋ {{ t.newScribble }}</button></header>
      <p class="notes-help">{{ t.notesHelp }}</p>
      <div class="note-groups">
        <section><h3>{{ t.scribbles }} <span>{{ scribbles.length }}</span></h3><button v-for="note in scribbles" :key="note.demo_note_id" type="button" :class="{ active: selectedId === note.demo_note_id }" @click="choose(note)"><strong>{{ note.tag || t.newScribble }}</strong><p>{{ note.content || '…' }}</p></button></section>
        <section><h3>{{ t.attachedNotes }} <span>{{ attached.length }}</span></h3><button v-for="note in attached" :key="note.demo_note_id" type="button" :class="{ active: selectedId === note.demo_note_id }" @click="choose(note)"><strong>{{ note.knowledge_label }}</strong><p>{{ note.content || '…' }}</p><small>{{ note.book_title }}</small></button></section>
      </div>
    </div>
  </section>
</template>
