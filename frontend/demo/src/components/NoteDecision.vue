<script setup>
import { nextTick, ref, watch } from "vue";
const props = defineProps({ t: Object, guard: Object });
const panel = ref(null);
let previousFocus;
watch(
  () => props.guard.pending.value,
  async (pending) => {
    if (pending) {
      previousFocus = document.activeElement;
      await nextTick();
      panel.value?.querySelector("button")?.focus();
    } else {
      await nextTick();
      previousFocus?.isConnected && previousFocus.focus();
    }
  },
);
function keyboard(event) {
  if (event.key === "Escape" && !props.guard.saving.value) {
    event.preventDefault();
    props.guard.cancel();
  }
  if (event.key !== "Tab") return;
  const buttons = [...panel.value.querySelectorAll("button:not(:disabled)")];
  if (!buttons.length) {
    event.preventDefault();
    return;
  }
  const target = event.shiftKey ? buttons.at(-1) : buttons[0];
  if (
    document.activeElement === (event.shiftKey ? buttons[0] : buttons.at(-1))
  ) {
    event.preventDefault();
    target.focus();
  }
}
</script>
<template>
  <div v-if="guard.pending.value" class="note-decision-backdrop">
    <section
      ref="panel"
      class="note-decision"
      role="dialog"
      aria-modal="true"
      :aria-label="t.unsavedWriting"
      @keydown="keyboard"
    >
      <h2>{{ t.unsavedWriting }}</h2>
      <p>{{ t.unsavedExplanation }}</p>
      <button
        type="button"
        :disabled="guard.saving.value"
        @click="guard.proceed(true)"
      >
        {{ t.saveContinue }}
      </button>
      <button
        type="button"
        :disabled="guard.saving.value"
        @click="guard.proceed(false)"
      >
        {{ t.discardContinue }}
      </button>
      <button
        type="button"
        :disabled="guard.saving.value"
        @click="guard.cancel"
      >
        {{ t.keepEditing }}
      </button>
    </section>
  </div>
</template>
<style scoped>
.note-decision-backdrop {
  position: fixed;
  inset: 0;
  background: #000b;
  display: grid;
  place-items: center;
  z-index: 1000;
}
.note-decision {
  max-width: 480px;
  margin: 20px;
  background: #202735;
  border: 1px solid #c5ad76;
  border-radius: 12px;
  padding: 24px;
  color: #f5f1e6;
}
.note-decision button {
  display: block;
  margin-top: 12px;
  width: 100%;
  padding: 10px;
  border: 1px solid #9da6bb;
  border-radius: 5px;
  background: #354154;
  color: inherit;
}
</style>
