import { computed, nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue';

// Crop presentation padding and manage zoom/pan without changing graph geometry.
export function useAtlasCamera(layout, viewport, scale, compact) {
  const frame = shallowRef({ width: 0, height: 0, left: 0, top: 0 });
  const bounds = computed(() => {
    const drawing = layout.value;
    if (!compact.value || !drawing.placed.length) return { x: 0, y: 0, width: drawing.width, height: drawing.height };
    const rectangles = [...drawing.parents, ...drawing.tiles, ...drawing.badges,
      ...drawing.placed.map(node => ({ x: node.x, y: node.y, w: 160, h: 64 }))];
    const points = [...rectangles.flatMap(rect => [{ x: rect.x, y: rect.y }, { x: rect.x + rect.w, y: rect.y + rect.h }]),
      ...drawing.edges.flatMap(edge => edge.points)];
    const x = Math.min(...points.map(point => point.x)) - 24;
    const y = Math.min(...points.map(point => point.y)) - 24;
    return { x, y, width: Math.max(...points.map(point => point.x)) + 24 - x,
      height: Math.max(...points.map(point => point.y)) + 24 - y };
  });
  const drawingWidth = computed(() => bounds.value.width * scale.value);
  const drawingHeight = computed(() => bounds.value.height * scale.value);
  function measure() {
    const el = viewport.value;
    if (!el) return;
    const measured = { width: el.clientWidth, height: el.clientHeight, left: el.scrollLeft, top: el.scrollTop };
    if (Object.keys(measured).some(key => measured[key] !== frame.value[key])) frame.value = measured;
  }
  async function center(selectedId) {
    await nextTick();
    const el = viewport.value;
    const node = layout.value.placed.find(item => String(item.knowledge_id) === String(selectedId));
    if (!el || !node) return;
    const padX = compact.value ? Math.max(0, (el.clientWidth - drawingWidth.value) / 2) : 0;
    const padY = compact.value ? Math.max(0, (el.clientHeight - drawingHeight.value) / 2) : 0;
    el.scrollLeft = Math.max(0, (node.x - bounds.value.x + 80) * scale.value + padX - el.clientWidth / 2);
    el.scrollTop = Math.max(0, (node.y - bounds.value.y + 32) * scale.value + padY - el.clientHeight / 2);
    measure();
  }
  function fit() {
    const el = viewport.value;
    if (!el) return;
    scale.value = Math.max(.2, Math.min(1.5, (el.clientWidth - 20) / bounds.value.width, (el.clientHeight - 20) / bounds.value.height));
  }
  const visible = computed(() => ({
    x: bounds.value.x + frame.value.left / scale.value,
    y: bounds.value.y + frame.value.top / scale.value,
    width: Math.min(bounds.value.width, frame.value.width / scale.value),
    height: Math.min(bounds.value.height, frame.value.height / scale.value),
  }));
  let observer;
  onMounted(() => {
    measure();
    observer = new ResizeObserver(measure);
    if (viewport.value) observer.observe(viewport.value);
  });
  onBeforeUnmount(() => observer?.disconnect());
  watch([drawingWidth, drawingHeight], () => nextTick(measure));
  return { bounds, drawingWidth, drawingHeight, visible, frame, center, fit, measure };
}
