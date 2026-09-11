<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
const props = defineProps<{
  id: string;
  title: string;
  open: boolean;
  active: boolean;
  order: number;
  offset: number;
  labels: Record<string, string>;
}>();
const emit = defineEmits<{ focus: []; close: [] }>();
const panel = ref<HTMLElement>();
const expanded = ref(false);
const left = ref(0),
  top = ref(0);
let drag: { x: number; y: number; left: number; top: number } | null = null;
function clamp() {
  if (!panel.value || innerWidth <= 700) return;
  const bounds = panel.value.parentElement!.getBoundingClientRect();
  left.value = Math.max(
    0,
    Math.min(left.value, bounds.width - panel.value.offsetWidth),
  );
  top.value = Math.max(0, Math.min(top.value, bounds.height - 40));
}
function start(event: PointerEvent) {
  if (
    event.button !== 0 ||
    innerWidth <= 700 ||
    expanded.value ||
    (event.target as Element).closest("button")
  )
    return;
  drag = {
    x: event.clientX,
    y: event.clientY,
    left: left.value,
    top: top.value,
  };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  event.preventDefault();
}
function move(event: PointerEvent) {
  if (drag) {
    left.value = drag.left + event.clientX - drag.x;
    top.value = drag.top + event.clientY - drag.y;
    clamp();
  }
}
function focusContent() {
  nextTick(() => panel.value?.focus({ preventScroll: true }));
}
watch(
  () => props.open,
  (value) => {
    if (value) {
      clamp();
      focusContent();
    }
  },
);
onMounted(() => {
  const bounds = panel.value!.parentElement!.getBoundingClientRect();
  left.value = Math.max(
    0,
    (bounds.width - panel.value!.offsetWidth) / 2 - 35 + props.offset * 22,
  );
  top.value = 10 + props.offset * 22;
  clamp();
  if (props.active) focusContent();
  addEventListener("resize", clamp);
});
onBeforeUnmount(() => removeEventListener("resize", clamp));
</script>
<template>
  <section
    v-show="open"
    ref="panel"
    class="window"
    :class="{ focused: active, maximized: expanded }"
    :data-page="id"
    :aria-label="title"
    tabindex="-1"
    :style="{ left: left + 'px', top: top + 'px', zIndex: order }"
    @pointerdown="emit('focus')"
    @focusin="!active && emit('focus')"
    @keydown.esc.stop.prevent="emit('close')"
  >
    <header
      class="window-title"
      @pointerdown="start"
      @pointermove="move"
      @pointerup="drag = null"
      @pointercancel="drag = null"
    >
      <span class="title-icon" aria-hidden="true">✧</span
      ><span>{{ title }}</span
      ><span class="title-lines" aria-hidden="true"></span>
      <button
        type="button"
        :aria-label="(expanded ? labels.restore : labels.expand) + ' ' + title"
        :aria-pressed="expanded"
        @click="expanded = !expanded"
      >
        □
      </button>
      <button
        type="button"
        :aria-label="labels.close + ' ' + title"
        @click="emit('close')"
      >
        ×
      </button>
    </header>
    <div class="window-body"><slot /></div>
  </section>
</template>
