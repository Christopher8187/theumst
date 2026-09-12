<script setup lang="ts">
import { computed } from 'vue';
import ContentsTree from '../../src/components/ContentsTree.vue';
import { buildContentsTree } from '../../src/domain/contents';
import { useWisdomI18n } from './i18n';
import type { SampleBook } from './books';
const props=defineProps<{book:SampleBook;selected:number|null;heading?:boolean}>();
defineEmits<{select:[id:number]}>();
const {t}=useWisdomI18n();
const tree=computed(()=>buildContentsTree(props.book.contents||[]).flatMap(section=>section.children.length&&(section.is_book_root||['','0'].includes(String(section.section_number??'')))?section.children:[section]));
</script>
<template>
  <section class="brief-contents" :class="{'short-contents':(book.contents?.length||0)<=48}" :aria-label="t.contents"><h3 v-if="heading">{{t.contents}}</h3><ContentsTree :t="t" :items="tree" :current-section-id="selected" @select="$emit('select',$event)"/></section>
</template>
<style scoped>
.brief-contents{padding:26px 28px;min-height:0;overflow:auto;color:#d6e4ec;scrollbar-width:thin;scrollbar-color:#94bccd70 transparent;font-family:'Segoe UI',sans-serif}.brief-contents>h3{font:400 24px Georgia,serif;margin:0 0 22px;color:#e4dae9}.brief-contents :deep(.contents-tree){list-style:none;margin:15px 0;padding:0}.brief-contents :deep(.contents-row){display:flex;align-items:center;gap:7px;min-height:45px;border-radius:3px}.brief-contents :deep(.contents-number){font:11px 'Courier New',monospace;color:#9bcbd6;flex-shrink:0}.brief-contents :deep(.contents-entry){font:13px/1.5 'Segoe UI',sans-serif;flex:1;overflow-wrap:anywhere}.brief-contents :deep(.contents-toggle){width:27px;min-width:27px;height:32px;padding:0;border:0;background:transparent;color:#cbb7df;font-size:17px;cursor:pointer}.brief-contents :deep(.contents-leaf){width:27px;flex-shrink:0;text-align:center;color:#779aaf}.brief-contents :deep(.contents-row.current){background:#acccdf19}.brief-contents :deep(.contents-window-summary){font:10px 'Courier New',monospace;color:#91aabd}.brief-contents :deep(.contents-row.current .contents-entry){color:#eff2f6}.brief-contents :deep(.contents-window-controls){display:flex;justify-content:space-between}.brief-contents :deep(.contents-window-controls button){background:#a7c7df14;border:1px solid #a7c7df33;color:#d8e9ef;padding:8px}
@media(max-width:700px){.brief-contents{padding:21px 18px}.brief-contents>h3{font-size:22px}.brief-contents :deep(.contents-entry){font-size:12px}.brief-contents :deep(.contents-row){min-height:44px;gap:4px}.brief-contents :deep(.contents-toggle){width:24px;min-width:24px}.brief-contents :deep(.contents-number){font-size:10px}}
</style>
<style scoped>
.short-contents :deep(.contents-window-summary){display:none}.brief-contents :deep(button:focus-visible){outline:1px solid #a9d2df;outline-offset:1px}
</style>
