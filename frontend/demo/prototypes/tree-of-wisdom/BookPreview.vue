<script setup lang="ts">
import katex from 'katex';
import BookCover from './BookCover.vue';
import type { SampleBook } from './books';
defineProps<{book:SampleBook;summoned:boolean;embedded?:boolean}>();
defineEmits<{close:[];summon:[];enter:[]}>();
const formula=(text:string)=>katex.renderToString(text,{throwOnError:false,trust:false,displayMode:true});
</script>
<template>
  <aside class="book-preview" :class="{embedded}" aria-label="Selected grimoire">
    <header class="preview-head"><span>Grimoire</span><span class="ruling"></span><button type="button" aria-label="Close grimoire preview" @click="$emit('close')">×</button></header>
    <div class="preview-scroll">
      <div class="preview-intro"><BookCover :book="book" small/><div><p class="eyebrow">{{book.subject}}</p><h2>{{book.title}}</h2><p class="edition">{{book.edition}}</p></div></div>
      <p class="summary">{{book.summary}}</p>
      <div class="contents-title"><h3>Within these pages</h3><span>{{book.count}} {{book.count===36?'objects':'passages'}}</span></div>
      <details v-for="(passage,i) in book.passages" :key="book.id+passage.title" class="passage">
        <summary><span class="passage-number">0{{i+1}}</span><span>{{passage.title}}<small>{{passage.kind}}</small></span><span class="expand">+</span></summary>
        <div class="passage-body"><p>{{passage.text}}</p><div v-if="passage.math" class="formula" v-html="formula(passage.math)"></div><details v-if="passage.answer" class="answer"><summary>Show answer</summary><p>{{passage.answer}}</p></details></div>
      </details>
    </div>
    <footer class="preview-footer"><span v-if="summoned" class="saved-note">✧ In your grimoires</span><button class="enter-button" type="button" @click="summoned?$emit('enter'):$emit('summon')">{{summoned?'Enter grimoire':'Summon grimoire'}}<span>↗</span></button></footer>
  </aside>
</template>
<style scoped>
.book-preview{width:370px;max-height:calc(100dvh - 170px);display:flex;flex-direction:column;background:#f0eddf;color:#2d444b;border:1px solid #99a8a5;box-shadow:5px 6px 0 #102c4270,0 20px 60px #050c2240;font-family:Georgia,serif}.preview-head{display:flex;align-items:center;gap:12px;padding:6px 7px 6px 13px;margin:4px;border:1px solid #a4b2ac;background:#dce3d9;font:12px 'Courier New',monospace}.ruling{flex:1;height:8px;border-top:3px double #a2b5af;border-bottom:3px double #a2b5af}.preview-head button{background:#f0eddf;border:1px solid #99aaa8;width:25px;height:24px;color:inherit;font-size:20px;cursor:pointer}.preview-scroll{overflow:auto;padding:25px 23px 10px;overscroll-behavior:contain}.preview-intro{display:flex;gap:23px;align-items:center}.eyebrow{font:9px/1.5 'Courier New',monospace;letter-spacing:.12em;text-transform:uppercase;color:#707b74;margin:0 0 8px}h2{font-size:27px;font-weight:400;line-height:1.1;margin:0 0 8px}.edition{font:10px/1.5 'Courier New',monospace;color:#717f7d;margin:0}.summary{font-size:14px;line-height:1.65;margin:25px 0 22px}.contents-title{display:flex;align-items:baseline;gap:12px;justify-content:space-between;margin-bottom:9px}.contents-title h3{font-size:15px;font-weight:400;margin:0}.contents-title span{font:9px 'Courier New',monospace;color:#74837d}.passage{border-top:1px solid #c7cebf}.passage>summary{display:flex;gap:11px;align-items:center;padding:12px 0;cursor:pointer;list-style:none;font-size:13px}.passage>summary::-webkit-details-marker{display:none}.passage-number{font:10px 'Courier New',monospace;color:#788981}.passage small{display:block;font:9px/1.5 'Courier New',monospace;color:#718079;margin-top:4px}.expand{margin-left:auto;font-size:18px;color:#7e8e86}.passage[open] .expand{transform:rotate(45deg)}.passage-body{font-size:13px;line-height:1.7;padding:0 4px 12px 25px}.passage-body p{margin:0 0 10px}.formula{overflow:auto;font-size:11px}.answer summary{font:11px 'Courier New',monospace;text-decoration:underline;text-underline-offset:3px;cursor:pointer}.answer p{margin-top:10px}.preview-footer{padding:14px 22px 19px;border-top:1px solid #c7cebf}.enter-button{display:flex;align-items:center;justify-content:space-between;width:100%;padding:12px 14px;border:1px solid #718b89;background:#274e5b;color:#faf4e4;cursor:pointer;font:12px 'Courier New',monospace}.enter-button:hover{background:#396573}.saved-note{display:block;font:10px 'Courier New',monospace;color:#667b6e;margin-bottom:10px}.embedded{width:100%;box-shadow:none;background:#f5f1e7ed;max-height:100%;border-color:#aaa797}.embedded .preview-head{background:#eae7d8}@media(max-width:700px){.book-preview{width:calc(100vw - 32px);max-height:calc(100dvh - 160px)}.preview-scroll{padding:18px}.preview-footer{padding:12px 18px}.embedded{width:100%}}
</style>
