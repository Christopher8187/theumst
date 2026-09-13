<script setup lang="ts">
// One expanding, connected pen drawing across the ruled projection.
import { computed, nextTick, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';
import { useWisdomI18n } from './i18n';
import type { SampleBook } from './books';
import { realms, type RealmId } from './realms';
import RealmDiagram from './RealmDiagram.vue';
import RealmContinuity from './RealmContinuity.vue';
import RealmDestination from './RealmDestination.vue';
import LanguageControl from './LanguageControl.vue';
import GrimoireCompletion from './GrimoireCompletion.vue';

const props = defineProps<{ book: SampleBook; reveal: number; ready: boolean; initialRealm?: RealmId }>();
const emit = defineEmits<{ back: []; realm: [value: RealmId | null] }>();
const { t } = useWisdomI18n();
const lastRealm = shallowRef<RealmId | null>(props.initialRealm ?? null);
const hoveredRealm = shallowRef<RealmId | null>(null);
const focusedRealm = shallowRef<RealmId | null>(null);
const enteringRealm = shallowRef<RealmId | null>(null);
const destination = shallowRef<RealmId | null>(props.initialRealm ?? null);
const returning = shallowRef(false);
const reforming = shallowRef(false);
const textPage = shallowRef(0);
const questionPage = shallowRef(0);
const note = shallowRef('');
const spread = useTemplateRef<HTMLDivElement>('spread');
const sheets = [realms.slice(0, 4), realms.slice(4)];
const activeRealm = computed(() => enteringRealm.value ?? hoveredRealm.value ?? focusedRealm.value);
const accent = computed(() => realms.find(realm => realm.id === activeRealm.value)?.accent ?? '#bfe6e9');
const busy = computed(() => !!enteringRealm.value || returning.value || reforming.value);
const motionStyle = computed(() => ({ opacity: props.reveal, transform: `translate3d(0,${(1-props.reveal)*110}px,0) rotateX(${(1-props.reveal)*32}deg) scale(${.82+.18*props.reveal})` }));
let timer: ReturnType<typeof setTimeout> | undefined;

function illuminate(event: PointerEvent, id: RealmId) {
  if (event.pointerType === 'mouse' && !busy.value) { focusedRealm.value = null; hoveredRealm.value = id; }
}
function focusRealm(id: RealmId) { hoveredRealm.value = null; focusedRealm.value = id; }
function activate(id: RealmId) {
  if (busy.value || !props.ready) return;
  lastRealm.value = id;
  enteringRealm.value = id;
  timer = setTimeout(() => {
    destination.value = id;
    enteringRealm.value = null;
    hoveredRealm.value = null;
    focusedRealm.value = null;
    emit('realm', id);
  }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 320);
}
async function returnToBook() {
  if (busy.value) return;
  returning.value = true;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  timer = setTimeout(async () => {
    destination.value = null;
    returning.value = false;
    reforming.value = true;
    emit('realm', null);
    await nextTick();
    timer = setTimeout(async () => {
      reforming.value = false;
      await nextTick();
      spread.value?.querySelector<HTMLButtonElement>(`[data-realm="${lastRealm.value}"]`)?.focus({ preventScroll: true });
    }, reduced ? 0 : 320);
  }, reduced ? 0 : 240);
}
function leave() { if (!busy.value) emit('back'); }
function escape() { if (destination.value) returnToBook(); else leave(); }
watch(() => props.ready, async ready => {
  if (ready && !destination.value) { await nextTick(); spread.value?.focus({ preventScroll: true }); }
}, { immediate: true });
onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
  <section class="altar-interface" :class="{'realm-entering':enteringRealm,'in-realm':destination,'returning-from-realm':returning,'book-reforming':reforming}" :style="{'--realm-accent':accent}" :inert="!ready" :aria-hidden="!ready" @keydown.esc.stop="escape">
    <div class="altar-nav" :inert="busy" :style="{opacity:reveal}"><button class="altar-return" :disabled="busy" @click="leave"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 5-7 7 7 7M3 12h17"/></svg>{{t.backToTree}}</button><LanguageControl/></div>
    <div v-show="!destination" class="book-projection" :style="motionStyle">
      <div class="projection-plinth" aria-hidden="true"><i></i><i></i></div>
      <div ref="spread" class="realm-spread" tabindex="-1" :aria-label="`${book.title} · ${t.realmBook}`">
        <div class="book-underleaf" aria-hidden="true"></div>
        <div class="book-spine" aria-hidden="true"><i></i></div>
        <section v-for="(sheet,page) in sheets" :key="page" class="realm-leaf" :class="page===0?'leaf-left':'leaf-right'">
          <header class="leaf-heading"><span v-if="page===0">{{book.title}}</span><GrimoireCompletion v-else class="realm-progress" :book="book" compact/><small>{{page===0?'Ⅰ':'Ⅱ'}}</small></header>
          <div class="leaf-diagrams">
            <RealmContinuity :page="page" :active="activeRealm"/>
            <button v-for="realm in sheet" :key="realm.id" class="realm-choice" :class="{'is-lit':activeRealm===realm.id}" :data-realm="realm.id" :style="{'--ink':realm.accent}" :aria-label="`${t.realmEnter} · ${t[realm.id]}`" :disabled="busy" @pointerenter="illuminate($event,realm.id)" @pointerleave="hoveredRealm=null" @focus="focusRealm(realm.id)" @blur="focusedRealm=null" @click="activate(realm.id)">
              <div class="drawing"><RealmDiagram :kind="realm.id"/></div>
              <span class="diagram-name"><span class="diagram-mark">{{realm.mark}}</span>{{t[realm.id]}}<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13m-5-5 5 5-5 5"/></svg></span>
            </button>
          </div>
        </section>
        <div class="spine-bookmark" aria-hidden="true"></div>
      </div>
    </div>
    <RealmDestination v-if="destination" :book="book" :realm="destination" :note="note" :page="destination==='questions'?questionPage:textPage" @back="returnToBook" @note="note=$event" @page="destination==='questions'?questionPage=$event:textPage=$event"/>
  </section>
</template>

<style scoped>
.altar-interface{position:fixed;inset:0;z-index:15;perspective:1600px;color:#e5edf0}
.altar-nav{position:absolute;top:22px;left:3%;right:3%;display:flex;justify-content:space-between;gap:20px;align-items:center;z-index:5}
.realm-progress{margin-left:auto;margin-right:18px;max-width:210px}.realm-progress :deep(.completion-label){display:none}.realm-progress :deep(.completion-copy){justify-content:flex-end}.realm-progress :deep(progress){height:2px}.realm-progress :deep(.completion-values strong){font:11px 'Courier New',monospace;color:#c0d9df}.realm-progress :deep(.completion-values small){color:#9fb7c6}
.altar-return{display:flex;align-items:center;gap:12px;min-height:44px;border:1px solid #c1d5df35;background:#173347c2;backdrop-filter:blur(15px);padding:10px 15px;color:#ddebf0;border-radius:3px;font:12px 'Bahnschrift','Segoe UI',sans-serif}
.altar-return svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.2}
.book-projection{position:absolute;inset:98px max(2.7%,calc((100vw - 1600px)/2)) 4.5%;display:flex;transform-origin:76% 83%;will-change:transform,opacity}
.realm-spread{position:relative;flex:1;display:grid;grid-template-columns:1fr 1fr;min-width:0;min-height:0;isolation:isolate;outline:none;filter:drop-shadow(0 22px 30px #132d3e40)}
.realm-leaf{display:flex;flex-direction:column;min-width:0;min-height:0;padding:20px 24px 16px;border:1px solid #c3e3e17d;background:linear-gradient(100deg,#183747ac,#163348c9);backdrop-filter:blur(20px) saturate(.74);box-shadow:inset 0 0 30px #9ecbda08;position:relative}
.realm-leaf::before{content:'';position:absolute;inset:64px 16px 16px;pointer-events:none;background:repeating-linear-gradient(transparent 0 31px,#a6ccda19 31px 32px)}
.realm-leaf::after{content:'';position:absolute;top:64px;bottom:18px;left:27px;border-left:1px solid #c6a2c735;pointer-events:none}
.leaf-left{border-radius:5px 14px 2px 5px;border-right-color:#d4e9ea21;transform:perspective(1800px) rotateY(1.3deg);transform-origin:right center}
.leaf-right{border-radius:14px 5px 5px 2px;border-left-color:#d4e9ea21;background:linear-gradient(90deg,#163348d4,#213747b8);transform:perspective(1800px) rotateY(-1.3deg);transform-origin:left center}
.leaf-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;color:#c9dce0;min-height:30px;padding:0 8px 12px;border-bottom:1px solid #c7e1e63c;z-index:1}
.leaf-heading>span{font:italic 16px/1.25 Georgia,serif;max-width:35ch}
.leaf-heading small{font:11px Georgia,serif;color:#a4c7cf}
.leaf-diagrams{position:relative;flex:1;min-height:0;margin-top:8px;z-index:1}
/* The connecting ink never intercepts navigation, and no hit areas overlap. */
.realm-choice{position:absolute;display:flex;flex-direction:column;align-items:stretch;justify-content:center;border:0;background:none;padding:3px 7px 8px;color:#c6d8df;min-width:44px;min-height:44px;cursor:pointer;isolation:isolate}
.realm-choice:disabled{cursor:default}
.realm-choice:focus-visible{outline:none}.realm-choice:focus-visible .diagram-name{outline:1px solid var(--ink);outline-offset:5px;border-radius:2px}
.drawing{width:100%;height:calc(100% - 29px);min-height:0;flex:1;transform:rotate(var(--tilt));color:#c9dce2;transition:color .18s,filter .18s;pointer-events:none}
.drawing :deep(svg){overflow:hidden}
.diagram-name{display:flex;align-items:center;gap:8px;align-self:center;position:relative;white-space:nowrap;font:italic 15px/1.4 Georgia,serif;min-height:28px;color:#dce5e8;transition:color .18s,text-shadow .18s}
.diagram-mark{font:18px/1 'Noto Serif CJK SC','SimSun',serif;color:var(--ink);opacity:.72}
.diagram-name>svg{width:16px;height:16px;flex-shrink:0;fill:none;stroke:var(--ink);stroke-width:1.2;opacity:0;pointer-events:none;transform:translateX(-4px);transition:opacity .18s,transform .18s}
.is-lit .drawing{color:var(--ink);filter:drop-shadow(0 0 2px var(--ink)) drop-shadow(0 0 9px color-mix(in srgb,var(--ink) 32%,transparent))}
.is-lit .diagram-name{color:#fff8f1;text-shadow:0 0 9px var(--ink)}
.is-lit .diagram-mark{opacity:1}
.is-lit .diagram-name>svg{opacity:1;transform:none}
.realm-choice[data-realm=text]{left:0;top:0;width:61%;height:49%;--tilt:-4deg}
.realm-choice[data-realm=questions]{right:0;top:12%;width:35%;height:39%;--tilt:7deg}
.realm-choice[data-realm=notes]{left:0;top:53%;width:46%;height:45%;--tilt:-6deg}
.realm-choice[data-realm=review]{right:1%;top:62%;width:44%;height:36%;--tilt:3deg}
.realm-choice[data-realm=preview]{left:0;top:0;width:49%;height:42%;--tilt:-5deg}
.realm-choice[data-realm=advice]{right:0;top:9%;width:44%;height:35%;--tilt:6deg}
.realm-choice[data-realm=expand]{left:0;top:48%;width:56%;height:51%;--tilt:-7deg}
.realm-choice[data-realm=progress]{right:0;top:49%;width:38%;height:47%;--tilt:4deg}
.realm-choice[data-realm=text] .diagram-name{align-self:flex-start;margin-left:24%}
.realm-choice[data-realm=questions] .diagram-name{align-self:flex-end;margin-right:8%}
.realm-choice[data-realm=notes] .diagram-name{align-self:flex-start;margin-left:18%}
.realm-choice[data-realm=preview] .diagram-name{align-self:flex-start;margin-left:12%}
.realm-choice[data-realm=expand] .diagram-name{align-self:flex-start;margin-left:29%}
.book-spine{position:absolute;z-index:4;top:3px;bottom:-7px;left:calc(50% - 9px);width:18px;background:linear-gradient(90deg,transparent,#071e3547 44%,#bde3e767 49%,#d9bfdfab 50%,#071e3565 60%,transparent);border-radius:50%;pointer-events:none}
.book-spine i{display:block;margin:auto;width:1px;height:100%;box-shadow:0 0 15px #c9b6e373}
.book-underleaf{position:absolute;inset:10px 3px -9px;border:1px solid #c1dfe56e;border-bottom:3px double #b3d8e68a;background:#1536494d;border-radius:4px;z-index:-1;transform:rotate(.2deg)}
.spine-bookmark{position:absolute;z-index:5;top:-6px;left:calc(50% + 13px);width:12px;height:56px;background:linear-gradient(#ccb3da92,#9cafcf2e);clip-path:polygon(0 0,100% 0,100% 100%,50% 88%,0 100%);border-top:1px solid #e5cceb}
.projection-plinth{position:absolute;bottom:-20px;left:69%;width:20%;height:16%;pointer-events:none;opacity:.45;background:conic-gradient(from -29deg at 50% 100%,transparent 0deg,#c4e7e71c 10deg,transparent 60deg);filter:blur(7px)}
.projection-plinth i{position:absolute;bottom:0;left:0;right:0;height:30px;border:1px solid #c4e4ed90;border-radius:50%;transform:rotate(-8deg);box-shadow:0 0 20px #acded544}
.projection-plinth i:last-child{inset:auto 12% 9px;height:15px;opacity:.5}
.realm-entering .realm-spread{animation:book-entry .32s both}
.in-realm .altar-return{visibility:hidden}
.returning-from-realm :deep(.realm-destination){animation:realm-destination-out .24s both;pointer-events:none}
.book-reforming .realm-spread{animation:book-reform .32s both}
@keyframes book-entry{0%,35%{opacity:1;transform:none}100%{opacity:0;transform:translateY(-8px) scale(1.025)}}
@keyframes book-reform{from{opacity:0;transform:translateY(12px) scale(.985)}to{opacity:1;transform:none}}
@keyframes realm-destination-out{from{opacity:1;transform:none}to{opacity:0;transform:translateY(15px)}}
@media(max-width:700px){
  .altar-nav{top:calc(15px + env(safe-area-inset-top));left:12px;right:12px;gap:10px}
  .realm-progress{margin-right:4px}.realm-progress :deep(.completion-values){gap:7px}.realm-progress :deep(.completion-values strong){font-size:10px}
  .altar-return{font-size:10px;padding:9px 10px;gap:7px}.altar-return svg{width:17px;height:17px}
  .book-projection{inset:calc(90px + env(safe-area-inset-top)) 9px max(24px,env(safe-area-inset-bottom))}
  .realm-leaf{padding:13px 8px 9px}.leaf-heading{padding:0 3px 10px;min-height:45px;gap:5px}.leaf-heading>span{font-size:12px}.leaf-heading small{font-size:9px}
  .realm-leaf::before{inset:67px 7px 10px}.realm-leaf::after{top:67px;left:11px}.leaf-diagrams{margin-top:4px}
  .realm-choice{padding:1px 2px 3px}.drawing{height:calc(100% - 27px)}
  .diagram-name{font-size:12px;gap:5px;min-height:25px}.diagram-mark{font-size:15px}.diagram-name>svg{display:none}
  .realm-choice .diagram-name{align-self:center!important;margin:0!important}
  .realm-choice[data-realm=text]{left:0;top:0;width:88%;height:23%}
  .realm-choice[data-realm=questions]{right:0;top:26%;width:87%;height:23%}
  .realm-choice[data-realm=notes]{left:0;top:52%;width:89%;height:23%}
  .realm-choice[data-realm=review]{right:0;top:78%;width:85%;height:21%}
  .realm-choice[data-realm=preview]{left:0;top:2%;width:91%;height:23%}
  .realm-choice[data-realm=advice]{right:0;top:28%;width:88%;height:22%}
  .realm-choice[data-realm=expand]{left:0;top:52%;width:91%;height:23%}
  .realm-choice[data-realm=progress]{right:0;top:78%;width:86%;height:21%}
  .book-spine{width:12px;left:calc(50% - 6px)}.spine-bookmark{left:calc(50% + 8px);width:8px;height:40px}
}
@media(max-width:360px){.book-projection{inset-inline:6px}.realm-leaf{padding-inline:5px}.leaf-heading>span{font-size:11px}.diagram-name{gap:4px}.diagram-mark{font-size:14px}}
@media(max-height:660px) and (min-height:501px){.book-projection{top:83px;bottom:18px}.realm-leaf{padding-top:10px}.leaf-heading{min-height:35px}.realm-leaf::before,.realm-leaf::after{top:57px}}
/* Short landscape retains the full drawing instead of shrinking its controls. */
@media(max-height:500px){.altar-interface{overflow-y:auto;overflow-x:hidden}.altar-nav{position:sticky;top:10px;margin:10px 3%;height:44px;left:auto;right:auto}.book-projection{position:relative;inset:auto;margin:20px 2.7% 25px;height:650px}.realm-spread{min-height:650px}}
@media(prefers-reduced-motion:reduce){.realm-spread,.drawing,.diagram-name,.diagram-name>svg{animation:none!important;transition:none}.returning-from-realm :deep(.realm-destination){animation:none}}
@media(max-width:700px) and (max-height:660px) and (min-height:501px){.book-projection{top:calc(83px + env(safe-area-inset-top))}}
</style>
