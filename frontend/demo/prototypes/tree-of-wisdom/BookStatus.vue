<script setup lang="ts">
import type { SampleBook } from './books';
import { useWisdomI18n } from './i18n';
defineProps<{book:SampleBook}>();
const {t}=useWisdomI18n();
</script>
<template>
  <span class="book-status" v-if="book.publisher||book.completed">
    <span v-if="book.publisher" class="book-publisher">{{book.publisher}}</span>
    <span v-if="book.completed" class="book-completion">{{book.completed}} / {{book.count}} · {{t.completed}}<progress :aria-label="t.progressLabel+' · '+book.title" :max="book.count" :value="book.completed"></progress></span>
  </span>
</template>
<style scoped>
.book-status{display:flex;flex-direction:column;gap:5px;margin-top:7px;max-width:23ch;font:8px/1.4 'Courier New',monospace;color:#c5c8dc;text-align:inherit}.book-publisher{overflow-wrap:anywhere}.book-completion{display:flex;flex-direction:column;gap:4px;color:#c3e4e9}.book-completion progress{width:100%;max-width:95px;align-self:center;height:3px;accent-color:#b7e6e5}@media(max-width:700px){.book-status{font-size:7px;gap:4px;max-width:19ch}}
</style>
