<script setup>
import { onMounted } from "vue";
import { useNoteEditor } from "../composables/useNoteEditor";
const props = defineProps({
  t: Object,
  node: Object,
  notes: Array,
  grimoireId: Number,
});
defineEmits(["close", "notes-page"]);
const { selected, tag, content, load, choose, save } = useNoteEditor();
const fresh = () => ({
  grimoire_id: props.grimoireId,
  knowledge_id: props.node?.knowledge_id,
  note_type: "attached",
  tag: "",
  content: "",
});
onMounted(() => load(props.notes[0] || fresh()));
function select(event) {
  choose(
    props.notes.find((n) => String(n.demo_note_id) === event.target.value) ||
      fresh(),
  );
  event.target.value = selected.value?.demo_note_id || "";
}
</script>
<template>
  <section class="note-panel">
    <header>
      <h2>{{ t.notes }}</h2>
      <button type="button" :aria-label="t.close" @click="$emit('close')">
        ×
      </button>
    </header>
    <label
      >{{ t.attachedNotes
      }}<select :value="selected?.demo_note_id || ''" @change="select">
        <option value="">{{ t.newNote }}</option>
        <option
          v-for="note in notes"
          :key="note.demo_note_id"
          :value="note.demo_note_id"
        >
          {{ note.tag || t.untitledNote }}
        </option>
      </select></label
    >
    <button type="button" @click="choose(fresh())">{{ t.newNote }}</button>
    <label>{{ t.tag }}<input v-model="tag" maxlength="120" /></label>
    <textarea
      v-model="content"
      :placeholder="t.notePlaceholder"
      :aria-label="t.notes"
    ></textarea>
    <div class="note-footer">
      <button type="button" class="ghost-button" @click="$emit('notes-page')">
        {{ t.allNotes }}</button
      ><button type="button" class="primary-button" @click="save">
        {{ t.saveNote }}
      </button>
    </div>
  </section>
</template>
