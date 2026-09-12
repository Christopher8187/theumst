<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue';
import katex from 'katex';
import { useWisdomI18n } from './i18n';
import type { SampleBook } from './books';
const props=defineProps<{book:SampleBook;page:number}>();
defineEmits<{turn:[page:number]}>();
const {t}=useWisdomI18n();
const answer=shallowRef(false);
const passage=computed(()=>props.book.passages[props.page]);
const formula=computed(()=>passage.value?.math?katex.renderToString(passage.value.math,{throwOnError:false,trust:false,displayMode:true}):'');
const chapters=computed(()=>(props.book.contents||[]).filter(section=>section.parent_section===null).map((section,i)=>({title:section.section_name,number:section.section_number,first:props.book.id==='analysis'?i:i*2})));
const chapter=computed(()=>chapters.value.filter(group=>group.first<=props.page).at(-1));
watch(()=>props.page,()=>answer.value=false);
</script>
<template>
  <section class="brief-extract" :aria-label="t.extract">
    <nav class="extract-chapters" :aria-label="t.chapters"><button v-for="group in chapters" :key="group.number" :aria-current="chapter?.number===group.number?'page':undefined" @click="$emit('turn',group.first)"><small>{{group.number}}</small><span>{{group.title}}</span></button></nav>
    <article v-if="passage" class="reading-page" :key="page" aria-live="polite" tabindex="0"><p class="passage-kind">{{passage.kind}}</p><h3>{{passage.title}}</h3><p>{{passage.text}}</p><div v-if="formula" class="reading-math" v-html="formula"></div><div v-if="passage.answer" class="answer-area"><button :aria-expanded="answer" @click="answer=!answer">{{answer?t.hideAnswer:t.revealAnswer}} <span>{{answer?'−':'+'}}</span></button><p v-if="answer">{{passage.answer}}</p></div></article>
    <p v-else class="reading-page">{{t.noExtract}}</p>
    <nav class="page-navigation" :aria-label="t.samplePages"><button :aria-label="t.previousPassage" :disabled="page===0" @click="$emit('turn',page-1)">←</button><div><button v-for="(entry,i) in book.passages" :key="i" :aria-label="t.samplePages+' '+(i+1)+': '+entry.title" :aria-current="page===i?'page':undefined" @click="$emit('turn',i)">{{i+1}}</button></div><button :aria-label="t.nextPassage" :disabled="page===book.passages.length-1" @click="$emit('turn',page+1)">→</button></nav>
  </section>
</template>
<style scoped>
.brief-extract{display:flex;flex-direction:column;min-height:0;min-width:0;color:#d7e5eb}.extract-chapters{display:flex;gap:6px;padding:15px 22px;border-bottom:1px solid #b8cbe321;flex-shrink:0;overflow:auto}.extract-chapters button{display:flex;align-items:center;gap:9px;min-width:0;flex:1;padding:9px;background:none;border:0;border-bottom:1px solid transparent;color:#aebdd0;text-align:left;min-height:44px}.extract-chapters button[aria-current]{color:#e3d1ec;border-bottom-color:#cab4df}.extract-chapters small{font:11px 'Courier New',monospace;color:#9cbacf}.extract-chapters span{font:11px/1.4 'Segoe UI',sans-serif}.reading-page{padding:28px 34px;min-height:0;flex:1;overflow:auto;scrollbar-width:thin;scrollbar-color:#94bccd70 transparent}.reading-page h3{font:400 30px/1.2 Georgia,serif;color:#ece2ea;margin:19px 0 22px;max-width:30ch;text-wrap:balance}.reading-page>p{font:15px/1.8 'Segoe UI',sans-serif;max-width:53ch;margin:0}.reading-page .passage-kind{font:10px 'Courier New',monospace;color:#bdb0cc;letter-spacing:.09em;text-transform:uppercase}.reading-math{font-size:16px;color:#b8e4ec;margin:25px 0;padding:12px 0;border-top:1px solid #b4ccdf20;overflow:auto}.answer-area{margin-top:21px}.answer-area button{border:1px solid #c6b5df40;background:#ac94c20c;color:#d8c4e4;padding:10px 13px;min-height:40px;font-size:12px;border-radius:4px}.answer-area button span{margin-left:12px}.answer-area p{font:14px/1.7 'Segoe UI',sans-serif;color:#cbd4e1;margin-top:18px}.page-navigation{display:flex;justify-content:space-between;align-items:center;padding:9px 23px;border-top:1px solid #c1cfe11c;flex-shrink:0}.page-navigation>div{display:flex;gap:5px}.page-navigation button{background:none;border:1px solid transparent;border-radius:50%;width:35px;min-height:35px;color:#b9c9d9;font:12px 'Courier New',monospace}.page-navigation>button{font-size:22px}.page-navigation button[aria-current]{background:#bcacd91d;border-color:#cbb4de70;color:#e9dced}.page-navigation button:disabled{opacity:.25;cursor:default}
@media(max-width:700px){.extract-chapters{padding:9px 15px}.extract-chapters button{padding:5px;gap:6px}.extract-chapters span{font-size:10px}.reading-page{padding:22px}.reading-page h3{font-size:27px;margin:17px 0 20px}.reading-page>p{font-size:14px;line-height:1.75}.reading-math{font-size:13px;margin:21px 0}.answer-area p{font-size:13px}.page-navigation{padding:7px 16px}.page-navigation button{min-height:39px;width:31px}}
@media(max-width:340px){.reading-page{padding:19px}.reading-page h3{font-size:24px}.reading-page>p{font-size:13px}.reading-math{font-size:12px}}
</style>
<style scoped>
.brief-extract button:focus-visible{outline:1px solid #a9d2df;outline-offset:2px}
</style>
