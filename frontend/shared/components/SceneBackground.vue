<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import artwork from "../assets/between-dimensions-final.png";
defineProps<{ label: string }>();
const emit = defineEmits<{ state: [value: any] }>();
const host = ref<HTMLElement>();
let controller: any,
  disposed = false;
onMounted(async () => {
  try {
    const { createScene } = await import("../composables/createScene.js");
    if (!disposed)
      controller = createScene(host.value!, artwork, (value) =>
        emit("state", value),
      );
  } catch {
    if (host.value) host.value.dataset.mode = "still";
  }
});
onBeforeUnmount(() => {
  disposed = true;
  controller?.dispose();
});
defineExpose({
  look: (direction: any) => controller?.look(direction),
  toggle: () => controller?.toggleRotation(),
  setting: (key: string, value: number) =>
    controller?.setSceneSetting(key, value),
  reset: () => controller?.resetScene(),
});
</script>
<template>
  <div
    id="scene"
    ref="host"
    role="img"
    :aria-label="label"
    :style="{ '--scene-art': `url(${artwork})` }"
  ></div>
  <div class="scene-shade" aria-hidden="true"></div>
  <div class="scene-grain" aria-hidden="true"></div>
</template>
