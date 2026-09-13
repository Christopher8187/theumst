<script setup lang="ts">
// Arrival samples let the new chooser be tried without redesigning later study views.
import { computed, nextTick, onMounted, useTemplateRef } from 'vue';
import type { SampleBook } from './books';
import { purposeKey, type RealmId } from './realms';
import { useWisdomI18n } from './i18n';
import BriefExtract from './BriefExtract.vue';
import RealmDiagram from './RealmDiagram.vue';
const props = defineProps<{ book: SampleBook; realm: RealmId; page: number; note: string }>();
const emit = defineEmits<{ back: []; page: [value: number]; note: [value: string] }>();
const { t } = useWisdomI18n();
const title = useTemplateRef<HTMLHeadingElement>('title');
const studyBook = computed(() => {
  if (props.realm !== 'questions') return props.book;
  const questions = props.book.passages.filter(p => p.kind === 'Exercise');
  return { ...props.book, contents: [], passages: questions.length ? questions : [{
    title: 'A sequence approaching zero', kind: 'Exercise',
    text: 'Show that the sequence aₙ = 1/n converges to zero. Given any ε > 0, how could you choose N so that |aₙ| < ε whenever n > N?',
    answer: 'Choose any integer N greater than 1/ε. For n > N, we have 0 < 1/n < 1/N < ε. This is precisely convergence to zero.',
  }] };
});
onMounted(async () => { await nextTick(); title.value?.focus({ preventScroll: true }); });
</script>

<template>
  <section class="realm-destination" @keydown.esc.stop="emit('back')" :aria-label="t[realm]">
    <header class="destination-header">
      <button @click="emit('back')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6M8 12h13"/></svg>{{t.realmReturn}}</button>
      <span>{{book.title}}</span>
    </header>
    <div class="destination-title"><h1 ref="title" tabindex="-1">{{t[realm]}}</h1><small>{{t.realmLocal}}</small></div>
    <BriefExtract v-if="realm==='text'||realm==='questions'" :book="studyBook" :page="page" @turn="emit('page',$event)"/>
    <div v-else-if="realm==='notes'" class="destination-notes"><textarea :value="note" :aria-label="t.notes" :placeholder="t.realmNotesHint" @input="emit('note',($event.target as HTMLTextAreaElement).value)"></textarea><small>{{t.realmNotesLocal}}</small></div>
    <div v-else class="destination-later"><RealmDiagram :kind="realm"/><p>{{t[purposeKey(realm)]}}</p><small>{{t.realmNext}}</small></div>
  </section>
</template>

<style scoped>
.realm-destination{position:absolute;inset:15% max(5%,calc((100vw - 1040px)/2)) 10%;display:flex;flex-direction:column;min-height:0;border:1px solid #b6d4dc60;background:#122b3bd6;backdrop-filter:blur(26px);border-radius:3px 14px 4px 4px;box-shadow:0 30px 80px #14243645;animation:destination-arrive .6s both;color:#ddeaf0}.destination-header{padding:15px 25px;border-bottom:1px solid #b5d8e12a;display:flex;gap:20px;justify-content:space-between;align-items:center;color:#b6cbd8;font:12px 'Bahnschrift','Segoe UI',sans-serif}.destination-header>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.destination-header button{display:flex;align-items:center;gap:9px;white-space:nowrap;background:none;border:0;color:#cae5ea;min-height:40px}.destination-header svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.3}.destination-title{display:flex;align-items:baseline;gap:18px;padding:23px 32px 13px}.destination-title h1{font:32px Georgia,serif;margin:0;color:#ede8ef;outline:none}.destination-title small,.destination-notes small,.destination-later small{font:11px/1.6 'Segoe UI',sans-serif;color:#b2c7d4}.destination-title small{margin-left:auto}.realm-destination :deep(.brief-extract){flex:1;overflow:hidden}.destination-notes{display:flex;flex:1;min-height:0;flex-direction:column;padding:12px 32px 26px;gap:13px}.destination-notes textarea{flex:1;min-height:100px;resize:none;border:0;border-top:1px solid #a9c8d132;border-bottom:1px solid #a9c8d132;background:repeating-linear-gradient(transparent 0 31px,#abcee314 31px 32px);color:#e3e5ef;padding:8px 12px;font:16px/32px Georgia,serif}.destination-later{display:flex;align-items:center;justify-content:center;flex-direction:column;padding:25px;text-align:center;flex:1;gap:16px}.destination-later :deep(svg){height:145px;width:235px;color:#badbe3}.destination-later p{font:22px/1.5 Georgia,serif;margin:0}.destination-later small{max-width:35ch}@keyframes destination-arrive{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}@media(max-width:700px){.realm-destination{inset:90px 12px 25px}.destination-header{padding:8px 14px;gap:15px}.destination-header>span{font-size:11px}.destination-title{padding:19px 21px 10px;gap:10px}.destination-title h1{font-size:27px}.destination-title small{font-size:10px}.destination-notes{padding:15px 21px 22px}}
</style>

<style scoped>
@media(max-height:500px){.realm-destination{position:relative;inset:auto;margin:20px 3%;height:520px}.destination-header{padding-block:8px}.destination-title{padding-top:13px}}
</style>
