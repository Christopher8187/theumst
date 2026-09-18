<script setup lang="ts">
import { computed } from 'vue';
import { notebookMathRows } from '../domain/notebook-math.js';

const props = defineProps<{ content?: string }>();
const rows = computed(() => notebookMathRows(props.content));
</script>

<template>
  <div class="notebook-math">
    <div v-for="(row, position) in rows" :key="position" class="notebook-math-row" :class="`notebook-${row.type}-row`" v-html="row.html"></div>
  </div>
</template>

<style scoped>
.notebook-text-row{line-height:30px;min-height:30px;background:repeating-linear-gradient(transparent 0 29px,var(--notebook-rule,#b9d5df2b) 29px 30px)}
.notebook-display-row{display:grid;place-items:center;min-height:30px;padding:3px 8px;border-bottom:1px solid var(--notebook-rule,#b9d5df2b);overflow-x:auto;overflow-y:hidden}
.notebook-display-row :deep(.katex-display){margin:0;padding:0;min-height:0;width:100%;max-width:100%;background:none;display:block;overflow-x:auto;overflow-y:hidden}
.notebook-display-row :deep(.katex-display>.katex){text-align:center}
</style>
