<script setup lang="ts">
import type { SampleBook } from './books';
import GrimoireCompletion from './GrimoireCompletion.vue';
import LanguageControl from './LanguageControl.vue';
defineProps<{ book: SampleBook }>();
</script>

<template>
  <div class="folio-status"><GrimoireCompletion class="folio-progress" :book="book" compact/><LanguageControl/></div>
</template>

<style scoped>
.folio-status{display:flex;align-items:center;justify-content:flex-end;gap:34px;flex:1;min-width:0}
.folio-status .folio-progress{flex:0 0 clamp(86px,14vw,210px);width:clamp(86px,14vw,210px);max-width:210px;min-width:0;margin:0}
.folio-status :deep(.completion-label){display:none}
.folio-status :deep(.completion-copy){justify-content:flex-end}
.folio-status :deep(progress){height:2px}
.folio-status :deep(.completion-values strong){font:11px 'Courier New',monospace;color:#c0d9df}
.folio-status :deep(.completion-values small){color:#9fb7c6}
.folio-status :deep(.language-control){height:32px;background:transparent;border-radius:3px;backdrop-filter:none}
@media(max-width:700px){.folio-status{gap:7px}.folio-status :deep(.completion-values){gap:7px}.folio-status :deep(.completion-values strong){font-size:10px}.folio-status :deep(.language-control){gap:3px;padding-inline:4px}.folio-status :deep(.language-control select){min-width:56px;padding-right:12px}.folio-status :deep(.language-mark){width:15px;height:15px}}
</style>
