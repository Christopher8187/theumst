<script setup lang="ts">
import type { SampleBook } from './books';
import { useWisdomI18n } from './i18n';
defineProps<{book:SampleBook;heading?:boolean;emblem?:boolean}>();
const {t}=useWisdomI18n();
</script>
<template>
  <section class="brief-summary" :aria-label="t.summary">
    <div v-if="emblem" class="summary-emblem" aria-hidden="true"><i></i><b>{{book.symbol}}</b><i></i></div>
    <h3 v-if="heading">{{t.summary}}</h3>
    <p>{{book.summary||book.title}}</p>
    <details class="book-details"><summary>{{t.bookDetails}} <span>＋</span></summary><dl><div><dt>{{t.edition}}</dt><dd>{{book.version||book.edition||t.unavailable}}</dd></div><div><dt>{{t.isbn}}</dt><dd>{{book.isbn||'—'}}</dd></div><div><dt>{{t.progress}}</dt><dd>{{book.completed||0}} / {{book.count}}</dd></div></dl></details>
  </section>
</template>
<style scoped>
.brief-summary{min-height:0;overflow:auto;padding:30px 34px;color:#d7e5eb;scrollbar-width:thin;scrollbar-color:#94bccd70 transparent}.brief-summary h3{font:400 29px/1.2 Georgia,serif;color:#eee3ee;margin:0 0 24px}.brief-summary>p{font:15px/1.85 'Segoe UI',sans-serif;margin:0;max-width:53ch}.summary-emblem{height:145px;position:relative;display:grid;place-items:center;color:#b3d7e6;margin:8px 0 31px}.summary-emblem b{font:72px Georgia,serif;font-weight:400;text-shadow:0 0 35px #a8c2e525}.summary-emblem i{position:absolute;width:126px;height:126px;border:1px solid #aacbe32a;border-radius:50%;transform:rotateX(50deg) rotateZ(-25deg)}.summary-emblem i:last-child{width:102px;height:102px;border-color:#d3b4de28;transform:rotateY(45deg) rotateZ(25deg)}.book-details{margin-top:30px;font:12px 'Segoe UI',sans-serif;color:#aabfd1;border-top:1px solid #bbcede27;padding-top:18px}.book-details summary{cursor:pointer;display:flex;justify-content:space-between;list-style:none;min-height:32px;align-items:center}.book-details summary::-webkit-details-marker{display:none}.book-details summary span{font-size:17px;color:#cdb8df}.book-details[open] summary span{transform:rotate(45deg)}.book-details dl{display:flex;flex-wrap:wrap;gap:20px 28px;margin:17px 0 0}.book-details dt{color:#a7b4c9;font-size:10px;margin-bottom:7px}.book-details dd{margin:0;color:#dce3ed;font-size:12px}
@media(max-width:700px){.brief-summary{padding:22px}.brief-summary>p{font-size:14px;line-height:1.75}.brief-summary h3{font-size:25px;margin-bottom:18px}.summary-emblem{height:110px;margin:0 0 23px}.summary-emblem b{font-size:60px}.summary-emblem i{width:105px;height:105px}.summary-emblem i:last-child{width:85px;height:85px}.book-details{margin-top:22px}}
</style>

<style scoped>
.book-details summary:focus-visible{outline:1px solid #a9d2df;outline-offset:4px}
</style>
