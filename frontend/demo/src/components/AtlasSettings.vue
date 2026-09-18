<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, shallowRef, useTemplateRef } from 'vue';

defineProps<{ compact: boolean; label?: string }>();
const open = shallowRef(false);
const root = useTemplateRef<HTMLElement>('root');
const trigger = useTemplateRef<HTMLButtonElement>('trigger');
function outside(event: PointerEvent) {
  if (event.target instanceof Node && !root.value?.contains(event.target)) open.value = false;
}
function focusOut(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !root.value?.contains(event.relatedTarget)) open.value = false;
}
async function dismiss() {
  if (!open.value) return;
  open.value = false;
  await nextTick();
  trigger.value?.focus();
}
onMounted(() => document.addEventListener('pointerdown', outside));
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside));
</script>

<template>
  <div ref="root" class="atlas-settings" :class="{'is-compact':compact}" @focusout="focusOut" @keydown.esc.stop.prevent="dismiss">
    <button v-if="compact" ref="trigger" class="atlas-settings-trigger" type="button"
      :aria-expanded="open" @click="open=!open">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6"/></svg>
      {{label}}
    </button>
    <div v-show="!compact || open" class="atlas-settings-panel" :role="compact?'group':undefined" :aria-label="compact?label:undefined">
      <slot/>
    </div>
  </div>
</template>

<style scoped>
.is-compact .atlas-settings-trigger{position:absolute;right:0;top:0;display:flex;align-items:center;gap:7px}
.atlas-settings-trigger svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round}
.is-compact .atlas-settings-panel{position:absolute;top:43px;right:0;z-index:6;width:min(350px,100%);padding:18px;background:#193746f7;border:1px solid #abcbdc73;border-radius:3px;box-shadow:0 12px 30px #071a3466;backdrop-filter:blur(22px)}
</style>
