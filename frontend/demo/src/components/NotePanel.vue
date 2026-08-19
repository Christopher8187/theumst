<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({ t: Object, node: Object, notes: Array, grimoireId: Number });
const emit = defineEmits(["close", "save", "notes-page"]);
const tag = ref("");
const content = ref("");
const currentId = ref(null);
const current = computed(() => props.notes.find(note => note.demo_note_id === currentId.value) || props.notes[0]);

watch(() => [props.node?.knowledge_id, props.notes], () => {
  const note = props.notes[0];
  currentId.value = note?.demo_note_id || null;
  tag.value = note?.tag || "";
  content.value = note?.content || "";
}, { immediate: true, deep: true });

function save() {
  emit("save", {
    id: current.value?.demo_note_id,
    grimoire_id: props.grimoireId,
    knowledge_id: props.node.knowledge_id,
    note_type: "attached",
    tag: tag.value,
    content: content.value
  });
}
</script>

<template>
  <section class="note-panel">
    <header><div><p>{{ t.knowledge }} #{{ node?.knowledge_id }}</p><h2>{{ t.notes }}</h2></div><button type="button" @click="$emit('close')">×</button></header>
    <label>{{ t.tag }}<input v-model="tag" maxlength="120" placeholder="rough-working"></label>
    <textarea v-model="content" :placeholder="t.notePlaceholder"></textarea>
    <div class="note-footer"><button type="button" class="ghost-button" @click="$emit('notes-page')">✎ {{ t.allNotes }}</button><button type="button" class="primary-button" @click="save">{{ t.saveNote }}</button></div>
  </section>
</template>
