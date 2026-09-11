import { computed, shallowRef } from "vue";

export function useDesktopWindows() {
  const windows = shallowRef([{ id: "home", open: true, order: 1 }]);
  let order = 1;
  const active = computed(
    () =>
      windows.value.filter((w) => w.open).sort((a, b) => b.order - a.order)[0]
        ?.id,
  );
  function open(id) {
    const found = windows.value.some((w) => w.id === id);
    windows.value = found
      ? windows.value.map((w) =>
          w.id === id ? { ...w, open: true, order: ++order } : w,
        )
      : [...windows.value, { id, open: true, order: ++order }];
  }
  function close(id) {
    windows.value = windows.value.map((w) =>
      w.id === id ? { ...w, open: false } : w,
    );
  }
  function toggle(id) {
    windows.value.some((w) => w.id === id && w.open) ? close(id) : open(id);
  }
  return { windows, active, open, close, toggle };
}
