import { computed, onBeforeUnmount, shallowRef } from 'vue';

export const smoothRange = (from: number, to: number, value: number) => {
  const t = Math.max(0, Math.min(1, (value - from) / (to - from)));
  return t * t * (3 - 2 * t);
};

// One reversible timeline controls the existing image, entrance, and rising book.
export function useAltarTravel(initiallyAtAltar: boolean) {
  const progress = shallowRef(initiallyAtAltar ? 1 : 0);
  const moving = shallowRef(false);
  let frame = 0;
  let completed: (() => void) | undefined;
  let target = progress.value;
  const pan = computed(() => smoothRange(.06, .8, progress.value));
  const entrance = computed(() => 1 - smoothRange(0, .16, progress.value));
  const book = computed(() => smoothRange(.7, 1, progress.value));

  function finish() {
    cancelAnimationFrame(frame);
    progress.value = target;
    moving.value = false;
    const callback = completed;
    completed = undefined;
    callback?.();
  }
  function travel(to: 0 | 1, done?: () => void) {
    cancelAnimationFrame(frame);
    const start = progress.value;
    target = to;
    completed = done;
    moving.value = true;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) { finish(); return; }
    const duration = 3600 * Math.abs(to - start);
    let began: number | undefined;
    function step(now: number) {
      began ??= now;
      const elapsed = Math.min(1, (now - began) / Math.max(1, duration));
      progress.value = start + (to - start) * elapsed;
      if (elapsed < 1) frame = requestAnimationFrame(step);
      else finish();
    }
    frame = requestAnimationFrame(step);
  }
  onBeforeUnmount(() => cancelAnimationFrame(frame));
  return { progress, moving, pan, entrance, book, travel, finish };
}
