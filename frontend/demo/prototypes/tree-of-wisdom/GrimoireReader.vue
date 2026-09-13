<script setup lang="ts">
import { shallowRef, onMounted, onBeforeUnmount } from 'vue';
import { useWisdomI18n } from './i18n';
import type { SampleBook } from './books';
import BriefSummary from './BriefSummary.vue';
import BriefContents from './BriefContents.vue';
// The Brief keeps summary and navigable contents together; reading begins in its realm.
const props=defineProps<{book:SampleBook;added:boolean}>();
const emit=defineEmits<{close:[];add:[];enter:[]}>();
const {t}=useWisdomI18n();
const dialog=shallowRef<HTMLDialogElement|null>(null);
const panel=shallowRef<'summary'|'contents'>(window.matchMedia('(max-width:700px)').matches?'summary':'contents');
const selectedSection=shallowRef<number|null>(props.book.id==='analysis'?5:110);
const previousFocus=document.activeElement as HTMLElement|null;
function selectSection(id:number){selectedSection.value=id}
onMounted(()=>dialog.value?.showModal());
onBeforeUnmount(()=>{dialog.value?.close();if(previousFocus?.isConnected)previousFocus.focus()});
</script>

<template>
  <dialog ref="dialog" class="brief-dialog" aria-labelledby="brief-title" @cancel.prevent="emit('close')" @click.self="emit('close')">
    <section class="brief-presentation">
      <header class="brief-heading">
        <h2 id="brief-title">{{book.title}}</h2>
        <button :aria-label="t.closeBrief" autofocus @click="emit('close')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M6 18 18 6"/></svg></button>
      </header>
      <div class="brief-workspace">
        <BriefSummary class="folio-summary" :class="{'mobile-hidden':panel!=='summary'}" :book="book" heading emblem/>
        <nav class="brief-tabs" :aria-label="t.brief">
          <span class="contents-heading">{{t.contents}}</span>
          <button class="summary-tab" :aria-current="panel==='summary'?'page':undefined" @click="panel='summary'">{{t.summary}}</button>
          <button class="contents-tab" :aria-current="panel==='contents'?'page':undefined" @click="panel='contents'">{{t.contents}}</button>
        </nav>
        <div class="folio-reading" :class="{'mobile-hidden':panel==='summary'}">
          <BriefContents :book="book" :selected="selectedSection" @select="selectSection"/>
        </div>
      </div>
      <footer class="brief-footer"><button @click="added?emit('enter'):emit('add')">{{added?t.enter:t.add}}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12"/></svg></button></footer>
    </section>
  </dialog>
</template>

<style scoped>
.brief-dialog{position:fixed;inset:0;margin:0;padding:0;width:100vw;height:100dvh;max-width:none;max-height:none;border:0;background:transparent;color:#e3eaf1;overflow:hidden;font-family:'Bahnschrift','Segoe UI',sans-serif;color-scheme:dark}
.brief-dialog::backdrop{background:#14273e4a;backdrop-filter:blur(5px)}
.brief-presentation{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;width:min(1120px,calc(100vw - 96px));height:min(690px,calc(100dvh - 96px));min-height:0;border:1px solid #b9d7e568;border-radius:5px 24px 6px 18px;background:linear-gradient(90deg,#243e50f5,#20374bf7 41.85%,#1c3247f7 42%,#253247f7);box-shadow:0 30px 100px #0b182f55,0 5px 0 -1px #26374d,0 6px 0 -1px #b2c7df52,inset 0 1px #d9e9ed20;backdrop-filter:blur(24px)}
.brief-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-shrink:0;min-height:86px;padding:18px 28px 18px 34px;border-bottom:1px solid #bfcede26}
.brief-heading h2{font:400 28px/1.2 Georgia,serif;letter-spacing:-.025em;margin:0;color:#eee6ef;text-wrap:balance}
.brief-heading>button{display:grid;place-items:center;flex:0 0 40px;width:40px;height:40px;border:1px solid transparent;border-radius:50%;background:none;color:#cfdee8;transition:background .18s,border-color .18s}
.brief-heading>button:hover{background:#c4ddea0b;border-color:#bcd6e53b}
.brief-heading svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.35;stroke-linecap:round}
.brief-workspace{position:relative;display:grid;grid-template-columns:42% 58%;grid-template-rows:49px minmax(0,1fr);min-height:0;flex:1}
.folio-summary{grid-column:1;grid-row:1 / 3;border-right:1px solid #b6d4df40;box-shadow:inset -12px 0 17px -17px #07152a;padding:28px 36px}
.brief-tabs{grid-column:2;grid-row:1;display:flex;gap:27px;align-items:stretch;padding:0 30px;border-bottom:1px solid #b5c9e326}
.contents-heading{position:relative;display:flex;align-items:center;color:#e9d8ef;font-size:12px}.contents-heading:after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#c8b4dc}
.brief-tabs button{position:relative;min-height:44px;padding:12px 0;background:none;border:0;color:#a4bdd0;font-size:12px;transition:color .18s}
.brief-tabs button:after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#c8b4dc;transform:scaleX(0);transition:transform .18s}
.brief-tabs button[aria-current]{color:#e9d8ef}.brief-tabs button[aria-current]:after{transform:scaleX(1)}
.summary-tab,.contents-tab{display:none}
.folio-reading{grid-column:2;grid-row:2;min-height:0;min-width:0;display:flex}.folio-reading>*{width:100%;flex:1}
.brief-footer{display:flex;justify-content:flex-end;flex-shrink:0;padding:15px 28px;border-top:1px solid #bdcfe32b;background:linear-gradient(90deg,transparent 42%,#101e310d 42%);border-radius:0 0 6px 18px}
.brief-footer button{display:flex;align-items:center;justify-content:space-between;gap:42px;min-width:176px;min-height:44px;padding:11px 15px;border:1px solid #b0d9e176;border-radius:4px 13px 4px 4px;background:#b2dce910;color:#d0edf1;font-size:12px;transition:background .18s,box-shadow .18s}
.brief-footer button:hover{background:#acdbe91d;box-shadow:0 0 20px #a2d8e411}.brief-footer svg{display:block;width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.25;stroke-linecap:round;stroke-linejoin:round}
button:focus-visible{outline:1px solid #b7dce6;outline-offset:3px}.brief-heading button:focus-visible{outline-offset:-4px}
.folio-summary :deep(.summary-emblem){height:96px;margin:0 0 25px}.folio-summary :deep(.summary-emblem i){width:96px;height:96px}.folio-summary :deep(.summary-emblem i:last-child){width:79px;height:79px}.folio-summary :deep(.summary-emblem b){font-size:54px;width:72px;height:72px;display:grid;place-items:center;line-height:1}
.folio-summary :deep(h3){font-size:26px;margin-bottom:19px}.folio-summary :deep(.book-details){margin-top:26px}
  .folio-reading :deep(.brief-contents){padding:22px 28px}.folio-reading :deep(.contents-tree){margin:7px 0}.folio-reading :deep(.contents-row){min-height:48px}
@media(max-width:700px){
  .brief-presentation{left:12px;right:12px;top:max(12px,env(safe-area-inset-top));bottom:max(18px,calc(12px + env(safe-area-inset-bottom)));width:auto;height:auto;transform:none;border-radius:4px 18px 5px 13px;background:linear-gradient(135deg,#233d50f7,#223148f7)}
  .brief-heading{min-height:75px;padding:15px 17px 15px 21px;gap:14px}.brief-heading h2{font-size:22px;line-height:1.25}.brief-heading>button{flex-basis:36px;width:36px;height:36px}
  .brief-workspace{grid-template-columns:minmax(0,1fr);grid-template-rows:49px minmax(0,1fr)}
  .brief-tabs{grid-column:1;grid-row:1;padding:0 21px;gap:25px}.contents-heading{display:none}.summary-tab,.contents-tab{display:block}.brief-tabs button{font-size:12px}
  .folio-summary,.folio-reading{grid-column:1;grid-row:2}.folio-summary{border-right:0;box-shadow:none;padding:27px 25px}.mobile-hidden{display:none}
  .folio-summary :deep(h3){display:none}.folio-summary :deep(.summary-emblem){height:110px;margin:5px 0 28px}.folio-summary :deep(.brief-summary>p){line-height:1.85}
  .brief-footer{padding:12px 18px}.brief-footer button{width:100%;min-height:46px}
  .folio-reading :deep(.brief-contents){padding:22px 18px}
}
@media(max-width:340px){.brief-heading h2{font-size:20px}.folio-summary{padding:24px 21px}.brief-tabs{gap:23px}}
@media(prefers-reduced-motion:reduce){*,*:after{transition:none!important}}
.folio-summary{padding:22px 32px}.folio-summary :deep(.summary-emblem){height:64px;margin:0 0 14px}.folio-summary :deep(.summary-emblem i){width:68px;height:68px}.folio-summary :deep(.summary-emblem i:last-child){width:54px;height:54px}.folio-summary :deep(.summary-emblem b){width:54px;height:54px;font-size:40px}.folio-summary :deep(h3){font-size:25px;margin-bottom:14px}.folio-summary :deep(>p){font-size:14px;line-height:1.7}.folio-summary :deep(.book-details){margin-top:20px;padding-top:12px}.folio-summary :deep(.book-details dl){margin-top:12px;gap:14px 24px}.folio-summary :deep(.book-details dt){text-transform:capitalize}
@media(max-width:700px){.folio-summary{padding:20px 23px}.folio-summary :deep(.summary-emblem){height:58px;margin:0 0 16px}.folio-summary :deep(>p){font-size:14px;line-height:1.65}.folio-summary :deep(.book-details){margin-top:18px}}
@media(max-width:700px) and (max-height:740px){.folio-summary{padding:17px 20px}.folio-summary :deep(.summary-emblem){display:none}.folio-summary :deep(>p){font-size:13px;line-height:1.6}.folio-summary :deep(.book-details){margin-top:14px;padding-top:8px}.folio-summary :deep(.book-details dl){gap:12px 20px}}
</style>
