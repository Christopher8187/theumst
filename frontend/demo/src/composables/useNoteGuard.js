import { ref, shallowRef } from "vue";
export function useNoteGuard(onError) {
  const editor = shallowRef(null),
    pending = shallowRef(null),
    saving = ref(false),
    running = ref(false);
  async function run(action) {
    if (pending.value || saving.value || running.value) return;
    if (editor.value?.dirty()) {
      pending.value = action;
      return;
    }
    running.value = true;
    try {
      await action();
    } catch (error) {
      onError(error);
    } finally {
      running.value = false;
    }
  }
  async function proceed(save) {
    if (saving.value) return;
    saving.value = true;
    try {
      if (save) await editor.value?.save();
      else editor.value?.discard();
      const action = pending.value;
      pending.value = null;
      if (action) await action();
    } catch (error) {
      onError(error);
    } finally {
      saving.value = false;
    }
  }
  return {
    editor,
    pending,
    saving,
    running,
    run,
    proceed,
    cancel: () => {
      pending.value = null;
    },
  };
}
