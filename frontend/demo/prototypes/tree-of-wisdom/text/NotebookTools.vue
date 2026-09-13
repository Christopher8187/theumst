<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef } from 'vue';

const props = defineProps<{
  labels: { crystallization: string; dependencies: string; notes: string; cluster: string };
  sideMode: string;
  discoveryKind: string;
}>();
const emit = defineEmits<{ action: [name: string] }>();
const tooltip = shallowRef<string | null>(null);
let hovered: string | null = null;
let focused: string | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
function cancelTimer() { clearTimeout(timer); timer = undefined; }
function enter(id: string, event: PointerEvent) {
  if (event.pointerType === 'touch') return;
  hovered = id;
  cancelTimer();
  if (tooltip.value) tooltip.value = id;
  else timer = setTimeout(() => { tooltip.value = id; }, 350);
}
function leave() {
  hovered = null;
  cancelTimer();
  timer = setTimeout(() => { tooltip.value = focused; }, 120);
}
function focus(id: string, event: FocusEvent) {
  if (!(event.target as HTMLElement).matches(':focus-visible')) return;
  cancelTimer();
  focused = id;
  tooltip.value = id;
}
function blur() {
  focused = null;
  if (!hovered) { cancelTimer(); tooltip.value = null; }
}
function dismiss() { cancelTimer(); focused = null; tooltip.value = null; }
function activate(id: string) { dismiss(); emit('action', id); }
onBeforeUnmount(cancelTimer);
const tools = computed(() => [
  { id: 'crystallize', label: props.labels.crystallization, path: 'm12 2 8 7-8 13L4 9Zm-8 7h16M12 2 8 9l4 13 4-13Z', active: props.sideMode === 'similar' && props.discoveryKind === 'crystallize' },
  { id: 'dependencies', label: props.labels.dependencies, path: 'M2 3h5v5H2ZM17 3h5v5h-5ZM9 16h6v5H9ZM4.5 8v4H12v4m7.5-8v4H12m-2 2 2 2 2-2', active: props.sideMode === 'similar' && props.discoveryKind === 'dependencies' },
  { id: 'notes', label: props.labels.notes, path: 'M15 4H5v16h14v-9M9 12l9-9 3 3-9 9-4 1ZM9 19h6', active: props.sideMode === 'notes' },
  { id: 'similar', label: props.labels.cluster, path: 'M9 7a3 3 0 1 0-6 0 3 3 0 0 0 6 0ZM21 8a3 3 0 1 0-6 0 3 3 0 0 0 6 0ZM15 19a3 3 0 1 0-6 0 3 3 0 0 0 6 0ZM9 7l6 1M8 10l3 6m5-5-3 5', active: props.sideMode === 'similar' && props.discoveryKind === 'similar' },
]);
const tooltipLabel = computed(() => tools.value.find(tool => tool.id === tooltip.value)?.label);
</script>

<template>
  <div class="notebook-tools" @keydown.esc.stop="dismiss">
    <div v-for="tool in tools" :key="tool.id" class="notebook-tool"
      @pointerenter="enter(tool.id,$event)" @pointerleave="leave">
      <button type="button" :aria-label="tool.label" :aria-pressed="tool.active"
        @focus="focus(tool.id,$event)" @blur="blur" @pointerdown="dismiss"
        @click="activate(tool.id)">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="tool.path"/></svg>
      </button>
    </div>
    <span class="notebook-tooltip" :class="{'is-visible':tooltipLabel}" aria-hidden="true">{{tooltipLabel}}</span>
  </div>
</template>

<style scoped>
.notebook-tools{display:flex;gap:5px;align-items:center;flex-shrink:0;padding:17px 0 5px;position:relative;z-index:4}
.notebook-tool{flex-shrink:0}
.notebook-tools button{display:grid;place-items:center;width:34px;height:34px;padding:6px;border:1px solid #b5d2d26b;border-radius:1px;background:transparent;color:#b7cfd5;cursor:pointer}
.notebook-tools button:hover,.notebook-tools button:focus-visible{background:#b4dadb16;color:#e8f1e9;border-color:#c7e6e2}
.notebook-tools button[aria-pressed=true]{color:#e0f3e8;background:#b3dcd42b;border-color:#c6e4de;box-shadow:inset 0 -2px #b5dbd4}
.notebook-tools button:focus-visible{outline:2px solid #cab9de;outline-offset:3px}
.notebook-tools svg{display:block;width:21px;height:21px;fill:none;stroke:currentColor;stroke-width:1.25;stroke-linecap:round;stroke-linejoin:round}
.notebook-tooltip{margin-left:9px;min-width:0;color:#c9d9d9;font:12px/1.35 'Segoe UI',sans-serif;pointer-events:none;opacity:0;transition:opacity .12s;overflow-wrap:anywhere}
.notebook-tooltip.is-visible{opacity:1}
@media(pointer:coarse){.notebook-tools button{width:40px;height:40px}}
@media(prefers-reduced-motion:reduce){.notebook-tooltip{transition:none}}
</style>
