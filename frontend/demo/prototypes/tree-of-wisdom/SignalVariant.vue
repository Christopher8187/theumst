<script setup lang="ts">
import type { SampleBook } from './books';
import GrimoireDetail from './GrimoireDetail.vue';
import { shallowRef } from 'vue';
const props=defineProps<{books:SampleBook[];selected?:SampleBook;added:boolean}>();
const emit=defineEmits<{select:[id:string];add:[];enter:[]}>();
const collapsed=shallowRef<string|null>(null);
const isOpen=(id:string)=>props.selected?.id===id && collapsed.value!==id;
function toggle(id:string){collapsed.value=isOpen(id)?id:null;emit('select',id)}
</script>

<template>
  <section class="signal-layout" aria-label="Signal interface"><p class="signal-heading">GRIMOIRES <span> / {{books.length.toString().padStart(2,'0')}}</span></p>
    <div class="signal-list"><div v-for="book in books" :key="book.id" class="signal-entry" :class="{active:isOpen(book.id)}"><button :aria-expanded="isOpen(book.id)" @click="toggle(book.id)"><span class="signal-icon">{{book.symbol}}</span><span class="signal-book"><small>{{book.subject}}</small><strong>{{book.title}}</strong></span><span class="signal-arrow">{{isOpen(book.id)?'−':'＋'}}</span></button><div v-if="isOpen(book.id)" class="signal-detail"><GrimoireDetail :book="book" :added="added" @add="$emit('add')" @enter="$emit('enter')"/></div></div></div>
  </section>
</template>

<style scoped>
.signal-layout{position:absolute;top:22%;bottom:17%;right:6%;width:37%;max-width:550px;overflow:auto;scrollbar-width:thin;scrollbar-color:#93c4d047 transparent;color:#e3f1f4;padding:0 5px 20px}.signal-heading{font:11px 'Bahnschrift','Segoe UI',sans-serif;letter-spacing:.13em;color:#d2e7eb;margin:0 0 21px;padding-bottom:15px;border-bottom:1px solid #c0e4ed40}.signal-heading span{color:#a8c9dd;font:9px 'Courier New',monospace;float:right}.signal-list{display:flex;flex-direction:column;gap:10px}.signal-entry{background:linear-gradient(95deg,#1b354bda,#252b40cf);border:1px solid #a2cfdf35;border-radius:4px 19px 4px 4px;backdrop-filter:blur(16px);transition:border-color .25s,background .25s;overflow:hidden}.signal-entry.active{border-color:#b1d1f096;background:linear-gradient(110deg,#213b50ed,#2a2b45ed);box-shadow:inset 2px 0 0 #bbeaf0,0 0 25px #d0bdd21a}.signal-entry>button{width:100%;display:flex;align-items:center;gap:17px;background:transparent;border:0;text-align:left;color:#e1eef3;padding:20px;cursor:pointer}.signal-icon{width:35px;flex-shrink:0;font:29px Georgia,serif;color:#c2cee8;text-align:center;text-shadow:0 0 15px #d8b7f056}.signal-book{display:flex;flex-direction:column;gap:5px}.signal-book small{font:8px 'Courier New',monospace;letter-spacing:.12em;text-transform:uppercase;color:#b3c6d4}.signal-book strong{font:16px/1.25 'Bahnschrift','Segoe UI',sans-serif;font-weight:400}.signal-arrow{margin-left:auto;font:17px 'Segoe UI',sans-serif;color:#c7b7e3}.signal-detail{padding:0 24px 26px 72px}.signal-detail :deep(.detail-heading){display:none}.signal-detail :deep(.grimoire-summary){font-size:12px}.signal-detail :deep(.summon-action){font-size:11px;gap:20px;min-height:38px}.signal-detail :deep(.detail-action){gap:10px}.signal-entry:not(.active):hover{background:#314159e8;border-color:#a5cbe980}@media(max-width:1000px){.signal-layout{width:49%;right:4%}}@media(max-width:700px){.signal-layout{position:relative;right:auto;top:auto;bottom:auto;width:auto;max-width:none;margin:165px 18px 140px;padding:0;overflow:visible}.signal-entry>button{padding:18px 14px;gap:10px}.signal-icon{width:30px}.signal-book strong{font-size:15px}.signal-detail{padding:0 18px 23px}.signal-heading{margin-bottom:14px}}
</style>
