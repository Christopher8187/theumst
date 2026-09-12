<script setup lang="ts">
import { computed, shallowRef, watch, onMounted, onBeforeUnmount } from 'vue';
import { useWisdomI18n } from './i18n';
import type { SampleBook } from './books';
import type { Variant, BriefDesign, ActionPlacement } from './designOptions';
import BriefSummary from './BriefSummary.vue';
import BriefContents from './BriefContents.vue';
import BriefExtract from './BriefExtract.vue';
import PrototypeSwitcher from './PrototypeSwitcher.vue';
// One reading state, three structurally different arrangements. The comparison bar is inside the modal.
const props=defineProps<{book:SampleBook;added:boolean;design:BriefDesign;variant:Variant;actions:ActionPlacement}>();
const emit=defineEmits<{close:[];add:[];enter:[];variant:[value:Variant]}>();
const {t}=useWisdomI18n();
const dialog=shallowRef<HTMLDialogElement|null>(null);
const panel=shallowRef<'summary'|'contents'|'extract'>(props.design==='A'?'contents':props.design==='B'?'extract':'summary');
const page=shallowRef(0);
const selectedSection=shallowRef<number|null>(props.book.id==='analysis'?1:110);
const mobilePage=shallowRef<'left'|'right'>(props.design==='B'?'right':'left');
const tabs=computed(()=>props.design==='A'?['contents','extract']:props.design==='B'?['summary','extract']:['summary','contents','extract']);
const previousFocus=document.activeElement as HTMLElement|null;
function turn(next:number){
  page.value=Math.max(0,Math.min(props.book.passages.length-1,next));
  const match=props.book.contents?.find(section=>section.section_name===props.book.passages[page.value]?.title);
  if(match)selectedSection.value=match.section_id;
}
function selectSection(id:number){
  selectedSection.value=id;
  const name=props.book.contents?.find(section=>section.section_id===id)?.section_name;
  const found=props.book.passages.findIndex(passage=>passage.title===name);
  if(found>=0){turn(found);panel.value='extract';mobilePage.value='right'}
}
function keydown(event:KeyboardEvent){
  event.stopPropagation();
  if((event.target as Element).closest('.round-switcher'))return;
  if(panel.value==='extract'&&!(event.target as Element).closest('.brief-contents')&&['ArrowLeft','ArrowRight'].includes(event.key)){
    event.preventDefault();turn(page.value+(event.key==='ArrowLeft'?-1:1));
  }
}
watch(()=>props.design,()=>{panel.value=props.design==='A'?'contents':props.design==='B'?'extract':'summary';mobilePage.value=props.design==='B'?'right':'left'});
onMounted(()=>dialog.value?.showModal());
onBeforeUnmount(()=>{dialog.value?.close();if(previousFocus?.isConnected)previousFocus.focus()});
</script>
<template>
  <dialog ref="dialog" class="brief-dialog" :class="'design-'+design" aria-labelledby="brief-title" @cancel.prevent="emit('close')" @keydown="keydown" @click.self="emit('close')">
    <section class="brief-presentation" :class="['brief-'+design,'mobile-'+mobilePage]">
      <header class="brief-heading"><h2 id="brief-title">{{book.title}}</h2><button :aria-label="t.closeBrief" autofocus @click="emit('close')">×</button></header>
      <nav v-if="design!=='C'" class="mobile-pages" :aria-label="t.brief"><button :aria-current="mobilePage==='left'?'page':undefined" @click="mobilePage='left'">{{design==='A'?t.summary:t.contents}}</button><button :aria-current="mobilePage==='right'?'page':undefined" @click="mobilePage='right'">{{design==='A'?t.read:t.summary+' / '+t.extract}}</button></nav>
      <div class="brief-workspace">
        <BriefSummary v-if="design==='A'" class="fixed-pane" :book="book" heading emblem/>
        <BriefContents v-if="design==='B'" class="fixed-pane" :book="book" :selected="selectedSection" heading @select="selectSection"/>
        <div class="changing-pane">
          <nav class="brief-tabs" :aria-label="t.brief"><button v-for="value in tabs" :key="value" :aria-current="panel===value?'page':undefined" @click="panel=value as typeof panel">{{t[value]}}</button></nav>
          <BriefSummary v-if="panel==='summary'" :book="book" />
          <BriefContents v-else-if="panel==='contents'" :book="book" :selected="selectedSection" @select="selectSection"/>
          <BriefExtract v-else :book="book" :page="page" @turn="turn"/>
        </div>
      </div>
      <footer class="brief-footer"><button @click="added?emit('enter'):emit('add')">{{added?t.enter:t.add}} <span>↗</span></button></footer>
    </section>
    <PrototypeSwitcher :value="variant" :brief="design" :actions="actions" @change="emit('variant',$event)"/>
  </dialog>
</template>
<style scoped>
.brief-dialog{position:fixed;inset:0;margin:0;padding:0;width:100vw;height:100dvh;max-width:none;max-height:none;border:0;background:transparent;color:#e3eaf1;overflow:hidden;font-family:'Bahnschrift','Segoe UI',sans-serif;color-scheme:dark}.brief-dialog::backdrop{background:#17263e65;backdrop-filter:blur(5px)}.brief-dialog.design-C::backdrop{background:linear-gradient(90deg,transparent 25%,#14243921 60%,#15233870);backdrop-filter:none}.brief-presentation{position:absolute;display:flex;flex-direction:column;overflow:hidden;background:#183245f2;border:1px solid #b0d6e56b;box-shadow:0 25px 90px #0b192952,inset 0 1px 0 #d0e7eb21;backdrop-filter:blur(24px);min-height:0}.brief-heading{display:flex;align-items:center;justify-content:space-between;gap:25px;padding:23px 29px;flex-shrink:0}.brief-heading h2{font:400 24px/1.2 'Bahnschrift','Segoe UI',sans-serif;letter-spacing:-.025em;margin:0}.brief-heading>button{color:#cbdbe5;background:none;border:0;font:27px 'Segoe UI',sans-serif;min-width:40px;min-height:40px}.brief-workspace{min-height:0;flex:1;display:grid}.changing-pane{display:flex;flex-direction:column;min-height:0;min-width:0}.changing-pane>:not(.brief-tabs){flex:1}.brief-tabs{display:flex;gap:22px;padding:0 29px;min-height:50px;align-items:stretch;border-bottom:1px solid #b4cce324;flex-shrink:0}.brief-tabs button{border:0;border-bottom:2px solid transparent;background:none;color:#9eb6c9;font:12px 'Bahnschrift','Segoe UI',sans-serif;padding:10px 0}.brief-tabs button[aria-current]{color:#e4d1eb;border-bottom-color:#c5b2d8}.brief-footer{display:flex;justify-content:flex-end;padding:15px 28px;border-top:1px solid #b4cbdc21;flex-shrink:0}.brief-footer button{display:flex;align-items:center;gap:35px;justify-content:space-between;background:#afdee712;color:#c3ebed;border:1px solid #b2dfe16b;border-radius:3px 12px 3px 3px;padding:11px 16px;min-height:43px;font-size:12px}.brief-A{width:min(1100px,calc(100vw - 100px));height:min(720px,calc(100dvh - 145px));left:50%;top:45%;transform:translate(-50%,-50%);border-radius:5px 23px 6px 16px;background:linear-gradient(105deg,#21384bf7,#1a3145f5 41%,#172c40f5 42%,#273046f5)}.brief-A .brief-heading{border-bottom:1px solid #b7c9df22}.brief-A .brief-workspace{grid-template-columns:42% 58%}.brief-A .fixed-pane{box-shadow:inset -7px 0 18px -17px #000;border-right:1px solid #a3d5dd50;padding:34px 40px}.brief-A .brief-heading h2{font:400 27px Georgia,serif}.brief-A .brief-footer{background:linear-gradient(90deg,transparent 42%,#141f351a 42%)}.brief-B{width:min(1160px,calc(100vw - 100px));height:min(690px,calc(100dvh - 150px));top:46%;left:50%;transform:translate(-50%,-50%);border-radius:4px 4px 23px 4px;background:linear-gradient(110deg,#1b3446f5,#203044f5)}.brief-B .brief-workspace{grid-template-columns:35% 65%}.brief-B .fixed-pane{background:#112a3a55;border-right:1px solid #b4cbdc26;padding-top:25px}.brief-B .brief-heading{border-bottom:1px solid #b4cbdc26}.brief-C{right:22px;top:22px;bottom:109px;width:min(490px,calc(100vw - 44px));border-radius:4px 4px 4px 22px;background:linear-gradient(125deg,#193749f2,#272f47f5);animation:drawer-enter .24s ease-out}.brief-C .brief-workspace{display:flex}.brief-C .changing-pane{width:100%}.brief-C .brief-heading{padding:22px 26px 15px}.brief-C .brief-heading h2{font-size:25px}.brief-C .brief-tabs{padding:0 27px}.brief-C .brief-footer button{width:100%}.mobile-pages{display:none}button:focus-visible{outline:2px solid #d5b7e4;outline-offset:3px}@keyframes drawer-enter{from{opacity:0;translate:22px 0}to{opacity:1;translate:0 0}}
@media(max-width:700px){.brief-presentation{top:12px;bottom:105px;left:12px;right:12px;width:auto;height:auto;transform:none;border-radius:4px 18px 4px 13px}.brief-heading,.brief-C .brief-heading{padding:17px 18px 14px;gap:14px}.brief-heading h2,.brief-A .brief-heading h2,.brief-C .brief-heading h2{font-size:20px;line-height:1.25}.brief-heading>button{min-width:35px}.mobile-pages{display:flex;flex-shrink:0;gap:5px;padding:0 16px 12px;border-bottom:1px solid #b4cbdc25}.mobile-pages button{min-height:39px;flex:1;background:none;border:1px solid #a9c4db29;color:#9db8cc;border-radius:3px;font-size:12px}.mobile-pages button[aria-current]{color:#e2d4ec;background:#c8bcda10;border-color:#c5b8d64d}.brief-A .brief-workspace,.brief-B .brief-workspace{display:flex}.brief-A .fixed-pane,.brief-B .fixed-pane{width:100%;border-right:0;padding:23px}.brief-presentation.mobile-left:not(.brief-C) .changing-pane{display:none}.brief-presentation.mobile-right .fixed-pane{display:none}.changing-pane{width:100%}.brief-A .fixed-pane :deep(.summary-emblem){height:100px;margin-bottom:24px}.brief-A .fixed-pane :deep(h3),.brief-B .fixed-pane :deep(h3){display:none}.brief-tabs,.brief-C .brief-tabs{padding:0 22px;min-height:44px;gap:25px}.brief-tabs button{font-size:12px}.brief-footer{padding:12px 18px}.brief-footer button{width:100%;min-height:43px}.brief-C .brief-workspace{min-height:0}.brief-C :deep(.summary-emblem){height:100px}.brief-B .brief-workspace{border-left:3px solid #bacce638}.brief-A .brief-workspace{background:linear-gradient(90deg,#7190a10a,transparent 6%,transparent 96%,#a8cad11c)}}
@media(prefers-reduced-motion:reduce){.brief-C{animation:none}}
</style>
<style scoped>
.brief-C :deep(.reading-math .katex-display){margin:.5em 0}.brief-C :deep(.brief-summary:after){content:'';width:120px;height:120px;border:1px solid #d2c2e814;border-radius:50%;box-shadow:0 0 0 14px #d2c2e804}
</style>
<style scoped>
.brief-C :deep(.brief-summary),.brief-C :deep(.reading-page){padding:24px}.brief-C :deep(.brief-summary>p),.brief-C :deep(.reading-page>p){font-size:14px}.brief-C :deep(.extract-chapters button){flex:0 0 auto;min-width:100px;max-width:155px}.brief-C :deep(.extract-chapters){scrollbar-width:thin}.brief-C :deep(.reading-page h3){font-size:28px}@media(max-width:700px){.brief-presentation{bottom:119px}.brief-C :deep(.brief-summary),.brief-C :deep(.reading-page){padding:21px}}
</style>
<style scoped>
.brief-A .fixed-pane{padding:25px 34px}.brief-A .fixed-pane :deep(.summary-emblem){height:96px;margin:0 0 25px}.brief-A .fixed-pane :deep(.summary-emblem i){width:91px;height:91px}.brief-A .fixed-pane :deep(.summary-emblem i:last-child){width:76px;height:76px}.brief-A .fixed-pane :deep(.summary-emblem b){font-size:55px}.brief-A .fixed-pane :deep(h3){font-size:26px;margin-bottom:18px}.brief-heading button:focus-visible{outline:1px solid #a0d6dfaa;outline-offset:-6px;border-radius:50%}.brief-C .brief-heading{padding:14px 22px 10px}.brief-C .brief-heading h2{font-size:23px}.brief-C .brief-tabs{min-height:42px;padding:0 24px}.brief-C .brief-footer{padding:10px 22px}.brief-C .brief-footer button{min-height:40px;padding:9px 14px}.brief-C :deep(.extract-chapters){padding:7px 17px}.brief-C :deep(.extract-chapters button){min-height:36px;padding:5px 6px}.brief-C :deep(.reading-page){padding:18px 24px}.brief-C :deep(.reading-page h3){font-size:26px;margin:14px 0 17px}.brief-C :deep(.reading-page>p){font-size:14px;line-height:1.65}.brief-C :deep(.reading-math){margin:16px 0 8px;padding:8px 0;font-size:14px}.brief-C :deep(.page-navigation){padding:5px 20px}.brief-C :deep(.page-navigation button){min-height:33px}.brief-C :deep(.brief-summary){position:relative;isolation:isolate}.brief-C :deep(.brief-summary:after){content:'';position:absolute;bottom:18px;right:35px;z-index:-1;pointer-events:none}
</style>
