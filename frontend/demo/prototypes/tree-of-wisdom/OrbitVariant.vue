<script setup lang="ts">
import {computed,nextTick,useTemplateRef} from 'vue';
import type {SampleBook} from './books';
import {useWisdomI18n} from './i18n';
import {useOrbitMotion} from './useOrbitMotion';
import ProjectedBook from './ProjectedBook.vue';
import GrimoireDetail from './GrimoireDetail.vue';
const props=defineProps<{books:SampleBook[];selected?:SampleBook;added:boolean}>();
const emit=defineEmits<{select:[id:string];add:[];enter:[];preview:[]}>();
const {t}=useWisdomI18n();
const stage=useTemplateRef<HTMLDivElement>('stage');
const selection=computed(()=>Math.max(0,props.books.findIndex(book=>book.id===props.selected?.id)));
const {positions}=useOrbitMotion(selection,computed(()=>props.books.length));
async function chooseByKey(event:KeyboardEvent){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const count=props.books.length;
  const next=event.key==='Home'?0:event.key==='End'?count-1:(selection.value+(event.key==='ArrowLeft'?-1:1)+count)%count;
  emit('select',props.books[next].id);await nextTick();stage.value?.querySelector<HTMLButtonElement>(`[data-book="${props.books[next].id}"]`)?.focus({preventScroll:true});
}
</script>
<template>
  <section class="orbit-layout" :aria-label="t.orbit">
    <div ref="stage" class="orbital-books orbit-volume-stage" @keydown="chooseByKey">
      <div class="orbit-track" aria-hidden="true"><i></i><i></i></div>
      <button v-for="(book,i) in books" :key="book.id" class="orbit-book" :class="{active:selected?.id===book.id}" :style="positions[i]" :data-book="book.id" :title="book.title" :aria-label="book.title" :aria-pressed="selected?.id===book.id" @click="emit('select',book.id)">
        <span class="orbital-mark" aria-hidden="true">{{String(i+1).padStart(2,'0')}}</span><ProjectedBook :book="book" large/><span class="orbital-title">{{book.title}}</span>
      </button>
    </div>
    <div class="orbit-details"><div class="orbit-detail-line" aria-hidden="true"><i></i><i></i></div><GrimoireDetail v-if="selected" :book="selected" :added="added" @add="emit('add')" @enter="emit('enter')" @preview="emit('preview')"/></div>
  </section>
</template>
<style scoped>
.orbit-layout{position:absolute;left:40%;right:4%;top:16%;bottom:10%;display:flex;flex-direction:column;min-height:0;color:#e4eef4}
.orbit-layout .orbital-books.orbit-volume-stage{--orbit-radius:clamp(140px,19vw,280px);position:relative;flex:0 0 auto;height:clamp(250px,40dvh,370px);min-height:0;perspective:1300px;perspective-origin:50% 42%;transform-style:preserve-3d}
.orbit-book{position:absolute;left:50%;top:49%;width:178px;display:flex;flex-direction:column;align-items:center;gap:13px;background:none;border:0;padding:0 6px;color:#dae8ee;transform:translate(-50%,-50%) translate3d(calc(var(--orbit-radius)*var(--arc-x)),var(--arc-y),var(--arc-z));transform-style:preserve-3d;opacity:var(--book-presence);cursor:pointer;will-change:transform}
.orbit-book:focus-visible{outline:none}.orbit-book:focus-visible .orbital-title{outline:1px solid #c3e4ee;outline-offset:6px;border-radius:2px}.orbital-mark{font:9px/1 'Courier New',monospace;color:#bcd3e7;letter-spacing:.16em;opacity:.65}
.orbital-title{font:13px/1.35 'Bahnschrift','Segoe UI',sans-serif;width:100%;min-height:2.7em;max-height:2.7em;overflow:hidden;text-align:center;text-wrap:balance;text-shadow:0 2px 10px #172639;margin-top:10px;word-break:normal;overflow-wrap:normal;color:#cad7e2;transition:color .2s}.active .orbital-title{color:#ecf5f6}.active .orbital-mark{color:#cfbce4;opacity:1}
.orbit-book :deep(.projected-book.large){--book-width:clamp(135px,12vw,168px)}.orbit-book :deep(.volume-front){transition:box-shadow .25s,border-color .25s}.active :deep(.volume-front){box-shadow:inset 0 0 25px #adcdef18,0 0 20px #beddf01f;border-color:#d5f0f4}.orbit-book:hover :deep(.volume-front){box-shadow:inset 0 0 30px #bbdcf023,0 0 26px #bfdaed33;border-color:#e2f9fd}
.orbit-track{position:absolute;left:4%;right:4%;top:calc(50% + 68px);height:67px;border:1px solid #bddcea24;border-bottom-color:#b7dce15e;border-radius:50%;transform:rotateX(40deg);pointer-events:none}.orbit-track i{position:absolute;inset:8px -15px -8px;border-bottom:1px solid #d2badd20;border-radius:50%}.orbit-track i:last-child{inset:-20px 12% 15px;border-color:#b8dfef1f}
.orbit-details{position:relative;flex:1;min-height:0;overflow:auto;padding:0 28px 22px;margin:8px 4% 0;background:linear-gradient(180deg,#192939e8,#222a42e3);border-radius:3px 3px 24px 3px;border-bottom:1px solid #afaee856;backdrop-filter:blur(18px);box-shadow:0 20px 50px #111d2b1f}.orbit-detail-line{display:flex;gap:15px;margin:0 -28px 18px;opacity:.55}.orbit-detail-line i{height:1px;flex:1;background:linear-gradient(90deg,transparent,#9fdbe7b0)}.orbit-detail-line i:last-child{background:linear-gradient(90deg,#d8bce6b0,transparent)}
.orbit-details :deep(.grimoire-detail){display:grid;grid-template-columns:1fr auto;gap:0 16px}.orbit-details :deep(.detail-heading),.orbit-details :deep(.grimoire-summary){grid-column:1/-1}.orbit-details :deep(.detail-heading h2){font-size:clamp(23px,2.2vw,29px);margin:5px 0 14px}.orbit-details :deep(.grimoire-summary){font-size:12px;line-height:1.65;margin-bottom:19px;max-width:65ch}.orbit-details :deep(.detail-action){grid-column:1;grid-row:3}.orbit-details :deep(.preview-action){grid-column:2;grid-row:3;margin:0;white-space:nowrap}.orbit-details :deep(.summon-action),.orbit-details :deep(.preview-action){font-size:12px}
@media(max-width:1050px) and (min-width:701px){.orbit-layout{left:32%;right:3%}.orbit-layout .orbital-books.orbit-volume-stage{--orbit-radius:19vw}.orbit-book{width:150px}.orbit-book :deep(.projected-book.large){--book-width:126px}.orbital-title{font-size:12px}}
@media(min-width:701px) and (max-height:740px){.orbit-layout .orbital-books.orbit-volume-stage{height:235px}.orbit-book{gap:8px}.orbit-book :deep(.projected-book.large){--book-width:120px}.orbital-title{font-size:12px;margin-top:6px}.orbit-details{padding-bottom:16px}.orbit-details :deep(.grimoire-summary){font-size:11px;line-height:1.5;margin-bottom:13px}.orbit-details :deep(.detail-heading h2){font-size:24px;margin-bottom:11px}}
@media(max-width:700px){
.orbit-layout{left:13px;right:13px;top:236px;bottom:26px}.orbit-layout .orbital-books.orbit-volume-stage{--orbit-radius:clamp(94px,33vw,180px);height:clamp(180px,28dvh,235px);perspective:1000px}.orbit-book{width:clamp(102px,31vw,144px);gap:8px;top:48%}.orbit-book :deep(.projected-book.large){--book-width:clamp(84px,23vw,116px);--book-thickness:12px}.orbit-book :deep(.large .volume-title){font-size:11px}.orbit-book :deep(.large .volume-symbol){font-size:33px}.orbit-book :deep(.large .volume-subject){font-size:6px}.orbit-book :deep(.volume-front){gap:5px}
.orbital-title{font-size:11px;line-height:1.3;min-height:2.6em;max-height:2.6em;margin-top:4px}.orbital-mark{font-size:8px}.orbit-track{top:calc(50% + 45px);height:42px}.orbit-details{margin:8px 0 0;padding:0 20px 19px}.orbit-detail-line{margin:0 -20px 14px}.orbit-details :deep(.grimoire-detail){display:flex;flex-direction:column}.orbit-details :deep(.detail-heading h2){font-size:25px;line-height:1.15}.orbit-details :deep(.grimoire-summary){font-size:12px;line-height:1.6;margin-bottom:18px}.orbit-details :deep(.summon-action){width:100%;min-height:44px}.orbit-details :deep(.preview-action){justify-content:center;min-height:44px;margin-top:9px}
}
@media(max-width:700px) and (max-height:740px){.orbit-layout .orbital-books.orbit-volume-stage{height:174px}.orbit-book :deep(.projected-book.large){--book-width:79px}.orbital-title{font-size:10px}.orbit-details :deep(.detail-heading h2){font-size:22px}.orbit-details :deep(.grimoire-summary){font-size:11px}}
@media(prefers-reduced-motion:reduce){.orbit-book,.orbital-title{will-change:auto;transition:none}}
</style>
