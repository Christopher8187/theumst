<script setup lang="ts">
defineProps<{
  labels: Record<string, string>;
  palette: string;
  language: string;
  scene: any;
}>();
const emit = defineEmits<{
  palette: [value: string];
  language: [value: string];
  setting: [key: string, value: number];
  reset: [];
  privacy: [];
}>();
const ranges = [
  ["speed", 0.1, 2, 0.05, "° / sec"],
  ["softness", 0, 100, 1, "%"],
  ["dust", 0, 100, 1, "%"],
  ["pixel", 0, 100, 1, "%"],
  ["fov", 65, 125, 1, "°"],
  ["perspective", 0, 60, 1, "%"],
] as const;
</script>
<template>
  <div class="settings-content">
    <div class="setting">
      <label for="colors"
        >{{ labels.colors
        }}<select
          id="colors"
          :value="palette"
          @change="emit('palette', ($event.target as HTMLSelectElement).value)"
        >
          <option value="paper">{{ labels.ivory }}</option>
          <option value="blue">{{ labels.blue }}</option>
        </select></label
      >
    </div>
    <div class="setting">
      <label for="language">
        <span class="setting-label">
          <svg class="language-symbol" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 5h12M9 3v2M12 5c-1 6-4 9-9 11M5 8c1 3 4 6 7 8M13 21l4-10 4 10M14.5 17h5" />
          </svg>
          {{ labels.language }}
        </span>
        <select
          id="language"
          :value="language"
          @change="emit('language', ($event.target as HTMLSelectElement).value)"
        >
          <option value="en">English</option>
          <option value="zh">中文</option>
          <option value="ja">日本語</option>
        </select></label
      >
    </div>
    <template v-if="scene?.settings"
      ><div
        v-for="[key, min, max, step, unit] in ranges"
        :key="key"
        class="setting"
      >
        <label :for="'scene-' + key"
          >{{ labels[key]
          }}<output>{{ scene.settings[key] }}{{ unit }}</output></label
        ><input
          :id="'scene-' + key"
          type="range"
          :min="min"
          :max="max"
          :step="step"
          :value="scene.settings[key]"
          @input="
            emit(
              'setting',
              key,
              Number(($event.target as HTMLInputElement).value),
            )
          "
        />
      </div>
      <div class="setting">
        <label for="quality"
          >{{ labels.quality
          }}<select
            id="quality"
            :value="scene.settings.quality"
            @change="
              emit(
                'setting',
                'quality',
                Number(($event.target as HTMLSelectElement).value),
              )
            "
          >
            <option :value="1">{{ labels.light }}</option>
            <option :value="1.5">{{ labels.balanced }}</option>
            <option :value="2">{{ labels.high }}</option>
          </select></label
        >
      </div>
      <button @click="emit('reset')">{{ labels.reset }}</button></template
    >
    <div class="settings-footer">
      <button class="quiet-link" @click="emit('privacy')">
        {{ labels.privacy }}</button
      ><small>Theumst 0.2.2</small>
    </div>
  </div>
</template>
