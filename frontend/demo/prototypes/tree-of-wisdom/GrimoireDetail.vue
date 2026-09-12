<script setup lang="ts">
import katex from 'katex';
import type { SampleBook } from './books';
defineProps<{book:SampleBook;added:boolean}>();
defineEmits<{add:[];enter:[]}>();
const formula=(value:string)=>katex.renderToString(value,{throwOnError:false,trust:false,displayMode:true});
</script>

<template>
  <section class="grimoire-detail" :key="book.id" aria-label="Selected grimoire">
    <div class="detail-heading"><p class="tech-label">{{book.subject}}<span>◦ {{book.count}} {{book.count===36?'objects':'passages'}}</span></p><h2>{{book.title}}</h2></div>
    <p class="grimoire-summary">{{book.summary}}</p>
    <div class="detail-action"><button class="summon-action" @click="added?$emit('enter'):$emit('add')"><span>{{added?'Enter grimoire':'Add grimoire'}}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></button><span class="added-state" :class="{added}">{{added?'✓ In your grimoires':'Available to add'}}</span></div>
    <details class="sample-reading"><summary>Look inside <span>＋</span></summary><div class="sample-passages"><article v-for="passage in book.passages" :key="passage.title"><small>{{passage.kind}}</small><h3>{{passage.title}}</h3><p>{{passage.text}}</p><div v-if="passage.math" class="math" v-html="formula(passage.math)"></div><details v-if="passage.answer" class="sample-answer"><summary>Show answer</summary><p>{{passage.answer}}</p></details></article></div></details>
  </section>
</template>

<style scoped>
.grimoire-detail{min-width:0;color:#e6f1f6;animation:detail-in .35s ease-out}.detail-heading h2{font:400 clamp(23px,2.35vw,35px)/1.08 'Bahnschrift','Segoe UI',sans-serif;letter-spacing:-.025em;margin:15px 0 18px;text-wrap:balance}.tech-label{font:9px/1.5 'Courier New',monospace;letter-spacing:.11em;text-transform:uppercase;color:#a5e0e7;margin:0;display:flex;gap:15px;flex-wrap:wrap}.tech-label span{letter-spacing:.025em;color:#b9b8d4}.grimoire-summary{font:13px/1.7 'Segoe UI',sans-serif;color:#c6d5df;margin:0 0 24px;max-width:48ch}.detail-action{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.summon-action{min-height:43px;display:flex;align-items:center;justify-content:space-between;gap:28px;border:1px solid #9beaf0a8;background:#8ce0eb16;color:#b6f7fa;box-shadow:inset 0 0 15px #9ee7ef0c;padding:11px 15px;cursor:pointer;border-radius:5px 15px 5px 5px;font:13px 'Bahnschrift','Segoe UI',sans-serif;transition:background .2s,box-shadow .2s}.summon-action:hover{background:#a5e8fa30;box-shadow:0 0 19px #9fe5ed24}.summon-action svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.6}.added-state{font:9px 'Courier New',monospace;color:#afa7c4}.added-state.added{color:#b6ddd2}.sample-reading{margin-top:24px;border-top:1px solid #a7c5dc29;padding-top:14px}.sample-reading>summary{font:11px 'Bahnschrift','Segoe UI',sans-serif;letter-spacing:.025em;cursor:pointer;display:flex;justify-content:space-between;color:#d7c6e7;list-style:none}.sample-reading>summary::-webkit-details-marker{display:none}.sample-reading[open]>summary>span{transform:rotate(45deg)}.sample-passages{padding-top:18px}.sample-passages article+article{margin-top:22px;padding-top:19px;border-top:1px solid #9ec1d31c}.sample-passages small{font:8px 'Courier New',monospace;color:#b4b0d6;text-transform:uppercase;letter-spacing:.14em}.sample-passages h3{font:17px/1.2 Georgia,serif;color:#e3e8f3;margin:7px 0 10px}.sample-passages p{font:12px/1.75 'Segoe UI',sans-serif;color:#c8d6e1;margin:0 0 8px}.math{font-size:11px;overflow:auto;color:#daf4f9}.sample-answer summary{font:10px 'Courier New',monospace;color:#d4aed5;cursor:pointer;margin:14px 0 8px}@keyframes detail-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style>
