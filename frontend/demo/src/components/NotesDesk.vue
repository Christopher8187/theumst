<script setup>
import { computed, inject, onMounted } from "vue";
import { useNoteEditor } from "../composables/useNoteEditor";
const props = defineProps({ t: Object, notes: Array, grimoireId: Number });
const emit = defineEmits(["delete"]);
const guard = inject("noteGuard");
const deleteNote = inject("deleteNote");
const { selected, tag, content, load, choose, save } = useNoteEditor();
const selectedId = computed(() => selected.value?.demo_note_id);
const scribbles = computed(() =>
  props.notes.filter((n) => n.note_type === "scribble"),
);
const attached = computed(() =>
  props.notes.filter((n) => n.note_type === "attached"),
);
const fresh = () => ({
  grimoire_id: props.grimoireId || null,
  knowledge_id: null,
  note_type: "scribble",
  tag: "",
  content: "",
});
const create = () => choose(fresh());
const remove = () =>
  guard.run(async () => {
    await deleteNote(selected.value);
    load(fresh());
  });
onMounted(() => load(fresh()));
</script>
<template>
  <section class="notes-desk">
    <div class="note-editor-pane">
      <header>
        <div>
          <p class="demo-kicker">{{ t.notesMode }}</p>
          <h1>{{ selected?.knowledge_label || (selected?.note_type === 'attached' ? t.sourceUnavailable : t.newScribble) }}</h1>
        </div>
        <span v-if="selected?.knowledge_id">#{{ selected.knowledge_id }}</span>
      </header>
      <label>{{ t.tag }}<input v-model="tag" maxlength="120" /></label>
      <textarea
        v-model="content"
        :placeholder="t.notePlaceholder"
        :aria-label="t.notes"
      ></textarea>
      <div class="note-editor-actions">
        <button
          v-if="selected?.demo_note_id"
          type="button"
          class="danger-text"
          @click="remove"
        >
          {{ t.delete }}
        </button>
        <button type="button" class="primary-button" @click="save">
          {{ t.saveNote }}
        </button>
      </div>
    </div>
    <div class="note-constellation-pane">
      <header>
        <div>
          <p class="demo-kicker">{{ t.personalWriting }}</p>
          <h2>{{ t.noteConstellation }}</h2>
        </div>
        <button type="button" class="ghost-button" @click="create">
          ＋ {{ t.newScribble }}
        </button>
      </header>
      <p class="notes-help">{{ t.notesHelp }}</p>
      <div class="note-groups">
        <section>
          <h3>
            {{ t.scribbles }} <span>{{ scribbles.length }}</span>
          </h3>
          <button
            v-for="note in scribbles"
            :key="note.demo_note_id"
            type="button"
            :class="{ active: selectedId === note.demo_note_id }"
            @click="choose(note)"
          >
            <strong>{{ note.tag || t.newScribble }}</strong>
            <p>{{ note.content || "…" }}</p>
          </button>
        </section>
        <section>
          <h3>
            {{ t.attachedNotes }} <span>{{ attached.length }}</span>
          </h3>
          <button
            v-for="note in attached"
            :key="note.demo_note_id"
            type="button"
            :class="{ active: selectedId === note.demo_note_id }"
            @click="choose(note)"
          >
            <strong>{{ note.knowledge_label || t.sourceUnavailable }}</strong>
            <p>{{ note.content || "…" }}</p>
            <small>{{ note.book_title || t.sourceUnavailable }}</small>
          </button>
        </section>
      </div>
    </div>
  </section>
</template>
