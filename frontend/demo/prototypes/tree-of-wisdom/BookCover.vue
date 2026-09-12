<script setup lang="ts">
import type { SampleBook } from './books';
defineProps<{book: SampleBook; small?: boolean}>();
</script>
<template>
  <div class="book-cover" :class="{small}" :style="{'--binding':book.color}" aria-hidden="true">
    <span class="cover-subject">{{book.subject}}</span><span class="cover-symbol">{{book.symbol}}</span>
    <span class="cover-name">{{book.title}}</span><span class="cover-foot">THEUMST</span>
  </div>
</template>
<style scoped>
.book-cover{--binding:#526c89;width:140px;height:190px;flex-shrink:0;background:linear-gradient(90deg,#0004,transparent 10%,#fff1 12%,transparent 16%),var(--binding);border-radius:2px 5px 5px 2px;color:#eee5c9;box-shadow:4px 4px 0 #e3dcc5,5px 5px 0 #7c776f,8px 13px 22px #06121d40;position:relative;display:flex;align-items:center;flex-direction:column;padding:22px 17px 12px;text-align:center;transform:rotate(-3deg);isolation:isolate}.book-cover:before{content:'';position:absolute;inset:10px 9px 9px 17px;border:1px solid #dfcc965e;pointer-events:none}.cover-subject{font:8px/1.4 'Courier New',monospace;text-transform:uppercase;letter-spacing:.15em}.cover-symbol{font:43px/1 Georgia,serif;margin:17px 0 10px}.cover-name{font:16px/1.2 Georgia,serif}.cover-foot{font:7px/1.4 'Courier New',monospace;letter-spacing:.25em;margin-top:auto}.small{width:72px;height:98px;padding:12px 8px 7px;box-shadow:2px 2px 0 #e3dcc5,3px 3px 0 #7c776f,3px 5px 12px #06121d30}.small:before{inset:5px 5px 5px 9px}.small .cover-subject,.small .cover-foot{font-size:4px}.small .cover-symbol{font-size:24px;margin:8px 0 4px}.small .cover-name{font-size:8px}
</style>
