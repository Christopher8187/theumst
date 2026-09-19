<script setup lang="ts">
import { computed } from 'vue';
import type { SampleBook } from './books';
import { bookCompletion } from './bookStats';
import { useWisdomI18n } from './i18n';

const props = withDefaults(defineProps<{ book: SampleBook; compact?: boolean }>(), { compact: false });
const { t } = useWisdomI18n();
const stats = computed(() => bookCompletion(props.book));
const accessibleLabel = computed(() => `${t.value.progressLabel}: ${stats.value.completed} / ${stats.value.total} · ${stats.value.percent}%`);
</script>

<template>
  <div class="grimoire-completion" :class="{ compact }">
    <div class="completion-copy">
      <span class="completion-label">{{t.progress}}</span>
      <span class="completion-values"><strong>{{stats.completed}} / {{stats.total}}</strong><small>{{stats.percent}}%</small></span>
    </div>
    <progress :aria-label="accessibleLabel" :max="stats.progressMax" :value="stats.completed"></progress>
  </div>
</template>

<style scoped>
.grimoire-completion{display:grid;width:100%;min-width:0;gap:8px;color:#dce8ec}.completion-copy{display:flex;align-items:baseline;justify-content:space-between;gap:15px;font:10px 'Segoe UI',sans-serif;color:#aebfce}.completion-values{display:flex;align-items:baseline;gap:12px;white-space:nowrap}.completion-values strong{font:400 12px 'Bahnschrift','Segoe UI',sans-serif;color:#dce8ec}.completion-values small{font:9px 'Courier New',monospace;color:#b7cadd}progress{display:block;width:100%;height:4px;border:0;border-radius:0;background:#9bbbc31c;overflow:hidden;appearance:none;-webkit-appearance:none;color:#a9dce4;accent-color:#a9dce4}progress::-webkit-progress-bar{background:#9bbbc31c}progress::-webkit-progress-value{background:linear-gradient(90deg,#8fc9d6,#b8dfe2 72%,#cbb9dc);box-shadow:0 0 8px #a9dce475}progress::-moz-progress-bar{background:linear-gradient(90deg,#8fc9d6,#b8dfe2 72%,#cbb9dc);box-shadow:0 0 8px #a9dce475}.compact{width:min(250px,100%);gap:6px}.compact .completion-copy{font-size:9px;gap:10px}.compact .completion-values{gap:9px}.compact .completion-values strong{font-size:11px}.compact progress{height:3px}
</style>
