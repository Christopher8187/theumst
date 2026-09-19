<script setup lang="ts">
defineProps<{ title: string; backLabel: string; disabled?: boolean }>();
defineEmits<{ back: [] }>();
</script>

<template>
  <div class="folio-navigation">
    <button class="folio-return" type="button" :disabled="disabled" :aria-label="backLabel" :title="backLabel" @click="$emit('back')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 5-7 7 7 7M3 12h17"/></svg><span>{{backLabel}}</span></button>
    <h1 class="folio-title">{{title}}</h1>
  </div>
</template>

<style scoped>
.folio-navigation{display:flex;align-items:center;gap:16px;min-width:0}
.folio-navigation .folio-return{display:flex;align-items:center;flex-shrink:0;gap:8px;min-height:32px;padding:0;border:0;background:transparent;backdrop-filter:none;color:#ddebf0;font:12px 'Bahnschrift','Segoe UI',sans-serif}
.folio-return svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.2}
.folio-navigation .folio-title{font:italic 16px/1.25 Georgia,serif;color:#c9dce0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;margin:0}
@media(max-width:700px){.folio-navigation{gap:5px}.folio-navigation .folio-return{min-width:28px}.folio-return span{display:none}.folio-return svg{width:17px;height:17px}.folio-navigation .folio-title{font-size:12px}}
@media(max-width:360px){.folio-navigation .folio-title{font-size:11px}}
</style>
