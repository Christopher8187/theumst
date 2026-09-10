import { inject, onBeforeUnmount, ref } from "vue";
export function useNoteEditor() {
  const guard = inject("noteGuard"),
    persist = inject("saveNote"),
    onError = inject("apiError");
  const selected = ref(null),
    tag = ref(""),
    content = ref("");
  let saving;
  const savingState = ref(false);
  let initial = { tag: "", content: "" };
  function load(note) {
    selected.value = note;
    tag.value = note?.tag || "";
    content.value = note?.content || "";
    initial = { tag: tag.value, content: content.value };
  }
  const editor = {
    saving: () => savingState.value,
    dirty: () => tag.value !== initial.tag || content.value !== initial.content,
    discard: () => {
      tag.value = initial.tag;
      content.value = initial.content;
    },
    save: () => {
      if (saving) return saving;
      savingState.value = true;
      const payload = {
        ...selected.value,
        id: selected.value?.demo_note_id,
        tag: tag.value,
        content: content.value,
      };
      saving = persist(payload)
        .then((result) => {
          selected.value = {
            ...payload,
            demo_note_id: result.note.demo_note_id,
          };
          initial = { tag: payload.tag, content: payload.content };
        })
        .finally(() => {
          saving = null;
          savingState.value = false;
        });
      return saving;
    },
  };
  guard.editor.value = editor;
  onBeforeUnmount(() => {
    if (guard.editor.value === editor) guard.editor.value = null;
  });
  return {
    selected,
    tag,
    content,
    load,
    choose: (note) => guard.run(() => load(note)),
    save: () => editor.save().catch(onError),
    editor,
  };
}
