<script setup lang="ts">
// One selected design: a symmetric ruled projection with eight drawn destinations.
import { computed, nextTick, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';
import { useWisdomI18n } from './i18n';
import type { SampleBook } from './books';
import { realms, purposeKey, type RealmId } from './realms';
import RealmDiagram from './RealmDiagram.vue';
import RealmDestination from './RealmDestination.vue';
import LanguageControl from './LanguageControl.vue';

const props = defineProps<{ book: SampleBook; reveal: number; ready: boolean; initialRealm?: RealmId }>();
const emit = defineEmits<{ back: []; realm: [value: RealmId | null] }>();
const { t } = useWisdomI18n();
const selected = shallowRef<RealmId | null>(props.initialRealm ?? null);
const destination = shallowRef<RealmId | null>(props.initialRealm ?? null);
const entering = shallowRef(false);
const returning = shallowRef(false);
const reforming = shallowRef(false);
const textPage = shallowRef(0);
const questionPage = shallowRef(0);
const note = shallowRef('');
const spread = useTemplateRef<HTMLDivElement>('spread');
const sheets = [realms.slice(0, 4), realms.slice(4)];
const chosen = computed(() => realms.find(realm => realm.id === selected.value));
const motionStyle = computed(() => ({ opacity: props.reveal, transform: `translate3d(0,${(1-props.reveal)*110}px,0) rotateX(${(1-props.reveal)*32}deg) scale(${.82+.18*props.reveal})` }));
let timer: ReturnType<typeof setTimeout> | undefined;

function activate(id: RealmId) {
  if (entering.value || returning.value || reforming.value || !props.ready) return;
  if (selected.value !== id) { selected.value = id; return; }
  entering.value = true;
  timer = setTimeout(() => {
    destination.value = id;
    entering.value = false;
    emit('realm', id);
  }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 420);
}
function keyboardActivate(event: KeyboardEvent, id: RealmId) {
  // Holding Enter must not count as a second deliberate activation.
  event.preventDefault();
  if (!event.repeat) activate(id);
}
async function returnToBook() {
  if (returning.value || entering.value) return;
  returning.value = true;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  timer = setTimeout(async () => {
    destination.value = null;
    returning.value = false;
    reforming.value = true;
    emit('realm', null);
    await nextTick();
    timer = setTimeout(() => {
      reforming.value = false;
      spread.value?.querySelector<HTMLButtonElement>(`[data-realm="${selected.value}"]`)?.focus({ preventScroll: true });
    }, reduced ? 0 : 320);
  }, reduced ? 0 : 240);
}
function leave() { if (!entering.value && !returning.value && !reforming.value) emit('back'); }
function escape() { if (destination.value) returnToBook(); else leave(); }
watch(() => props.ready, async ready => {
  if (ready && !destination.value) { await nextTick(); spread.value?.focus({ preventScroll: true }); }
}, { immediate: true });
onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
  <section class="altar-interface" :class="{'realm-entering':entering,'in-realm':destination,'returning-from-realm':returning,'book-reforming':reforming}" :style="{'--realm-accent':chosen?.accent||'#bfe6e9'}" :inert="!ready" :aria-hidden="!ready" @keydown.esc.stop="escape">
    <div class="altar-nav" :style="{opacity:reveal}"><button class="altar-return" @click="leave"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 5-7 7 7 7M3 12h17"/></svg>{{t.backToTree}}</button><LanguageControl/></div>
    <div v-show="!destination" class="book-projection" :style="motionStyle">
      <div class="projection-plinth" aria-hidden="true"><i></i><i></i></div>
      <div ref="spread" class="realm-spread" tabindex="-1" :aria-label="`${book.title} · ${t.realmBook}`">
        <div class="book-underleaf" aria-hidden="true"></div>
        <div class="book-spine" aria-hidden="true"><i></i></div>
        <section v-for="(sheet,page) in sheets" :key="page" class="realm-leaf" :class="page===0?'leaf-left':'leaf-right'">
          <header class="leaf-heading"><span v-if="page===0">{{book.title}}</span><span v-else aria-hidden="true"></span><small>{{page===0?'Ⅰ':'Ⅱ'}}</small></header>
          <div class="leaf-diagrams">
            <svg class="page-wander" viewBox="0 0 400 360" preserveAspectRatio="none" aria-hidden="true"><path v-if="page===0" d="M19 148q77 42 176-6M268 49l17-5m-10 0 2 8M60 333l103-7m-67-4 1 9"/><path v-else d="M14 150q58 27 133-10M212 195q43-13 91-8m-20-4 1 9M302 28l26 6m-15-8-2 11"/></svg>
            <button v-for="realm in sheet" :key="realm.id" class="realm-choice" :class="{'is-selected':selected===realm.id}" :data-realm="realm.id" :style="{'--ink':realm.accent}" :aria-pressed="selected===realm.id" :aria-label="selected===realm.id?`${t[realm.id]} · ${t.realmEnter}`:t[realm.id]" @click="activate(realm.id)" @keydown.enter="keyboardActivate($event,realm.id)">
              <div class="drawing"><RealmDiagram :kind="realm.id"/></div>
              <span class="diagram-name"><span class="diagram-mark">{{realm.mark}}</span>{{t[realm.id]}}<svg v-if="selected===realm.id" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13m-5-5 5 5-5 5"/></svg></span>
              <i class="selection-underline" aria-hidden="true"></i>
            </button>
          </div>
        </section>
        <div class="spine-bookmark" aria-hidden="true"></div>
      </div>
      <footer class="realm-caption" aria-live="polite">
        <template v-if="selected"><div><span>{{t[selected]}}</span><p>{{t[purposeKey(selected)]}}</p></div><button :disabled="entering" @click="activate(selected)">{{t.realmEnter}}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6"/></svg></button></template>
        <span v-else class="unselected-caption">{{t.realmChoose}}</span>
      </footer>
    </div>
    <RealmDestination v-if="destination" :book="book" :realm="destination" :note="note" :page="destination==='questions'?questionPage:textPage" @back="returnToBook" @note="note=$event" @page="destination==='questions'?questionPage=$event:textPage=$event"/>
  </section>
</template>

<style scoped>
.altar-interface{position:fixed;inset:0;z-index:15;perspective:1600px;color:#e5edf0}.altar-nav{position:absolute;top:26px;left:4.5%;right:4.5%;display:flex;justify-content:space-between;align-items:center;z-index:5}.altar-return{display:flex;align-items:center;gap:12px;min-height:44px;border:1px solid #c1d5df35;background:#173347c2;backdrop-filter:blur(15px);padding:10px 15px;color:#ddebf0;border-radius:3px;font:12px 'Bahnschrift','Segoe UI',sans-serif}.altar-return svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.2}.book-projection{position:absolute;inset:17% max(5%,calc((100vw - 1130px)/2)) 7%;display:flex;flex-direction:column;transform-origin:76% 83%;will-change:transform,opacity}.realm-spread{position:relative;flex:1;display:grid;grid-template-columns:1fr 1fr;min-height:0;isolation:isolate;outline:none;transition:transform .4s,opacity .4s;filter:drop-shadow(0 22px 30px #132d3e40)}.realm-leaf{display:flex;flex-direction:column;min-width:0;min-height:0;padding:22px 30px 24px;border:1px solid #c3e3e17d;background:linear-gradient(100deg,#183747ab,#163348ce);backdrop-filter:blur(20px) saturate(.74);box-shadow:inset 0 0 30px #9ecbda08;position:relative}.realm-leaf::before{content:'';position:absolute;inset:70px 18px 16px;pointer-events:none;background:repeating-linear-gradient(transparent 0 29px,#a6ccda21 29px 30px)}.realm-leaf::after{content:'';position:absolute;top:71px;bottom:18px;left:30px;border-left:1px solid #c6a2c743;pointer-events:none}.leaf-left{border-radius:5px 14px 2px 5px;border-right-color:#d4e9ea21;transform:perspective(1800px) rotateY(2deg);transform-origin:right center}.leaf-right{border-radius:14px 5px 5px 2px;border-left-color:#d4e9ea21;background:linear-gradient(90deg,#163348d9,#213747b8);transform:perspective(1800px) rotateY(-2deg);transform-origin:left center}.leaf-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;color:#c9dce0;min-height:34px;padding:0 8px 15px 13px;border-bottom:1px solid #c7e1e651;z-index:1}.leaf-heading>span{font:italic 16px/1.25 Georgia,serif;max-width:31ch}.leaf-heading small{font:11px Georgia,serif;color:#a4c7cf}.leaf-right .leaf-heading>span{font:10px 'Courier New',monospace;letter-spacing:.08em}.leaf-diagrams{min-height:0;flex:1;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:9px 12px;padding-top:14px;z-index:1}.realm-choice{position:relative;border:0;background:none;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;padding:12px 8px 17px;color:#bfd0d7;min-width:0;min-height:0;border-radius:0;transition:color .25s,background .25s}.realm-choice:hover{color:var(--ink);background:#b7deec08}.realm-choice:focus-visible{outline:1px solid var(--ink);outline-offset:-5px}.drawing{height:clamp(70px,12dvh,127px);width:min(100%,180px);position:relative;padding-bottom:14px}.drawing :deep(svg){max-height:105px}.diagram-formula{position:absolute;bottom:-1px;right:9%;font:italic 11px Georgia,serif;letter-spacing:.06em;opacity:.58;transform:rotate(-4deg);color:var(--ink)}.diagram-name{display:flex;gap:10px;align-items:center;justify-content:center;font:13px 'Bahnschrift','Segoe UI',sans-serif;min-height:24px;position:relative;color:#cfdde3}.diagram-mark{font:19px/1 'Noto Serif CJK SC','SimSun',serif;color:var(--ink);opacity:.72}.diagram-name>svg{width:15px;height:15px;fill:none;stroke:var(--ink);stroke-width:1.2;position:absolute;left:calc(100% + 9px)}.selection-underline{position:absolute;height:1px;bottom:6px;left:20%;right:20%;background:var(--ink);opacity:0;transform:scaleX(.15);transition:transform .3s,opacity .3s}.is-selected{color:var(--ink);background:radial-gradient(ellipse at center,#aadeec15,transparent 72%)}.is-selected .drawing :deep(svg){filter:drop-shadow(0 0 5px var(--ink));transform:translateY(-2px)}.is-selected .drawing :deep(g){animation:ink-wake .45s both}.is-selected .diagram-name{color:#f0f3f2}.is-selected .diagram-mark{opacity:1}.is-selected .selection-underline{opacity:.85;transform:scaleX(1)}.book-spine{position:absolute;z-index:4;top:3px;bottom:-7px;left:calc(50% - 9px);width:18px;background:linear-gradient(90deg,transparent,#071e3547 44%,#bde3e767 49%,#d9bfdfab 50%,#071e3565 60%,transparent);border-radius:50%;pointer-events:none}.book-spine i{display:block;margin:auto;width:1px;height:100%;box-shadow:0 0 15px #c9b6e373}.book-underleaf{position:absolute;inset:10px 3px -9px;border:1px solid #c1dfe56e;border-bottom:3px double #b3d8e68a;background:#1536494d;border-radius:4px;z-index:-1;transform:rotate(.25deg)}.spine-bookmark{position:absolute;z-index:5;top:-6px;left:calc(50% + 13px);width:12px;height:56px;background:linear-gradient(#ccb3da92,#9cafcf2e);clip-path:polygon(0 0,100% 0,100% 100%,50% 88%,0 100%);border-top:1px solid #e5cceb}.projection-plinth{position:absolute;bottom:40px;left:69%;width:20%;height:16%;pointer-events:none;opacity:.6;background:conic-gradient(from -29deg at 50% 100%,transparent 0deg,#c4e7e71c 10deg,transparent 60deg);filter:blur(7px)}.projection-plinth i{position:absolute;bottom:0;left:0;right:0;height:30px;border:1px solid #c4e4ed90;border-radius:50%;transform:rotate(-8deg);box-shadow:0 0 20px #acded544}.projection-plinth i:last-child{inset:auto 12% 9px;height:15px;opacity:.5}.realm-caption{position:relative;display:flex;align-items:center;justify-content:space-between;gap:25px;min-height:89px;padding:21px 26px 0;color:#e6eef0;text-shadow:0 1px 9px #1d344bdd}.realm-caption>div{min-width:0;padding:8px 16px;background:#122a3f9e;backdrop-filter:blur(12px);border-left:1px solid var(--realm-accent)}.realm-caption>div>span{font:16px Georgia,serif;color:var(--realm-accent)}.realm-caption p{font:12px/1.5 'Segoe UI',sans-serif;margin:5px 0 0;color:#d2dfe7}.realm-caption>button{flex-shrink:0;display:flex;align-items:center;gap:25px;min-height:44px;border:1px solid var(--realm-accent);background:#163548ce;color:#e0f0f1;backdrop-filter:blur(16px);padding:11px 19px;font:12px 'Bahnschrift','Segoe UI',sans-serif;transition:background .25s,box-shadow .25s}.realm-caption>button:hover{background:#294f60ef;box-shadow:0 0 20px #b9e2e826}.realm-caption>button svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.25}.unselected-caption{margin:auto;font:italic 13px Georgia,serif;color:#dfe6ed;background:#163247a8;padding:9px 20px;backdrop-filter:blur(12px)}.realm-entering .realm-spread{transform:translateY(-10px) scale(1.035);opacity:0}.realm-entering .realm-caption{opacity:0;transition:opacity .3s}.in-realm .altar-return{visibility:hidden}@keyframes ink-wake{from{opacity:.5;stroke-dasharray:8 3}to{opacity:1;stroke-dasharray:8 0}}
@media(min-width:701px) and (max-height:760px){.book-projection{top:15%;bottom:5%}.realm-leaf{padding-top:16px;padding-bottom:16px}.leaf-diagrams{padding-top:5px;gap:3px 9px}.drawing{height:90px}.realm-caption{min-height:81px;padding-top:17px}}
@media(max-width:700px){.altar-nav{top:calc(18px + env(safe-area-inset-top));left:16px;right:16px;gap:12px}.altar-return{font-size:10px;padding:9px 10px;gap:7px}.altar-return svg{width:17px;height:17px}.book-projection{inset:120px 12px max(24px,env(safe-area-inset-bottom));transform-origin:78% 84%}.realm-leaf{padding:15px 10px 10px}.leaf-heading{padding:0 4px 12px;min-height:48px;gap:5px}.leaf-heading>span{font-size:12px}.leaf-heading small{font-size:9px}.leaf-right .leaf-heading>span{font-size:9px;letter-spacing:0}.realm-leaf::before{inset:66px 8px 12px;background-size:auto 25px}.realm-leaf::after{left:12px;top:66px}.leaf-diagrams{grid-template-columns:1fr;grid-template-rows:repeat(4,1fr);padding-top:9px;gap:2px}.realm-choice{gap:1px;padding:2px 8px 7px;flex-direction:row;justify-content:flex-start}.drawing{width:55%;height:65px;padding-bottom:9px;flex-shrink:0}.diagram-formula{font-size:8px;right:0;bottom:0}.diagram-name{font-size:10px;flex-direction:column;gap:6px;min-width:0;flex:1}.diagram-mark{font-size:18px}.diagram-name>svg{display:none}.selection-underline{left:18%;right:12%;bottom:3px}.book-spine{width:12px;left:calc(50% - 6px)}.spine-bookmark{left:calc(50% + 8px);width:8px;height:40px}.realm-caption{min-height:102px;padding:19px 3px 0;gap:12px}.realm-caption>div{padding:6px 9px}.realm-caption>div>span{font-size:14px}.realm-caption p{font-size:10px;line-height:1.5}.realm-caption>button{padding:10px 13px;gap:12px;font-size:11px}.realm-caption>button svg{width:17px;height:17px}.unselected-caption{font-size:12px}.projection-plinth{bottom:75px}}
@media(max-width:360px){.altar-nav{left:12px;right:12px;gap:7px}.altar-return{font-size:9px;padding:8px;gap:5px}.book-projection{inset-inline:8px;top:112px}.realm-leaf{padding-inline:7px}.realm-choice{flex-direction:column;gap:0;padding:3px 6px 8px}.drawing{height:55px;width:91px;max-width:100%}.diagram-name{flex-direction:row;flex:none;font-size:10px;gap:6px;min-height:21px}.diagram-mark{font-size:15px}.realm-caption{min-height:100px;gap:7px}.realm-caption p{font-size:9px}.realm-caption>button{padding:10px;gap:8px}}
@media(max-height:660px){.book-projection{top:92px;bottom:13px}.realm-caption{min-height:77px;padding-top:14px}.realm-caption p{display:none}.drawing{height:55px}.leaf-heading{min-height:30px}.realm-leaf{padding-top:9px}.realm-leaf::before,.realm-leaf::after{top:45px}}
</style>

<style scoped>
/* Uneven margin doodles, composed separately rather than in rows or columns. */
.leaf-diagrams{display:block;position:relative;padding:0;margin:8px 0 0}.page-wander{position:absolute;inset:0;width:100%;height:100%;fill:none;stroke:#c9cfdd;stroke-width:.8;stroke-linecap:round;opacity:.22;pointer-events:none}.realm-choice{position:absolute;flex-direction:column;justify-content:center;padding:8px 4px 14px;gap:2px;transform:rotate(var(--tilt));isolation:isolate;min-width:44px;min-height:44px}.realm-choice:hover{background:radial-gradient(ellipse,#bad2e70d,transparent 70%)}.realm-choice .drawing{width:100%;height:calc(100% - 30px);padding:0;max-width:230px;flex:1;min-height:0}.realm-choice .drawing :deep(svg){max-height:none}.diagram-name{font:italic 15px/1.25 Georgia,serif;flex-direction:row;flex:none;gap:8px;min-height:25px;max-width:100%;text-align:center}.diagram-mark{font-size:18px}.selection-underline{bottom:6px;height:5px;border-bottom:1px solid var(--ink);border-radius:50%;background:none;left:28%;right:25%}.realm-choice[data-realm=text]{left:1%;top:1%;width:52%;height:44%;--tilt:-5deg}.realm-choice[data-realm=questions]{right:0;top:24%;width:43%;height:39%;--tilt:7deg}.realm-choice[data-realm=notes]{left:0;top:53%;width:50%;height:44%;--tilt:-7deg}.realm-choice[data-realm=review]{right:1%;top:69%;width:40%;height:30%;--tilt:3deg}.realm-choice[data-realm=preview]{left:0;top:9%;width:46%;height:41%;--tilt:-6deg}.realm-choice[data-realm=advice]{right:0;top:0;width:45%;height:37%;--tilt:6deg}.realm-choice[data-realm=expand]{left:3%;top:56%;width:46%;height:43%;--tilt:-9deg}.realm-choice[data-realm=progress]{right:0;top:43%;width:43%;height:49%;--tilt:5deg}.realm-leaf{background:linear-gradient(100deg,#183747a3,#163348bd)}.leaf-right{background:linear-gradient(90deg,#163348c9,#213747ad)}.leaf-right .leaf-heading>span{font:20px Georgia,serif;color:#cab8d591}.realm-choice.is-selected{background:radial-gradient(ellipse,#c4ddea13,transparent 73%)}
@media(max-width:700px){.realm-choice{padding:5px 1px 11px}.realm-choice .drawing{width:100%;height:calc(100% - 36px);min-height:0;max-width:160px;flex:1}.diagram-name{font:italic 12px/1.3 Georgia,serif;gap:5px;flex-wrap:wrap;min-height:30px}.diagram-mark{font-size:16px}.realm-choice[data-realm=text]{left:1%;top:0;width:73%;height:24%;--tilt:-5deg}.realm-choice[data-realm=questions]{right:0;top:25%;width:73%;height:23%;--tilt:6deg}.realm-choice[data-realm=notes]{left:0;top:50%;width:74%;height:25%;--tilt:-6deg}.realm-choice[data-realm=review]{right:0;top:77%;width:72%;height:23%;--tilt:3deg}.realm-choice[data-realm=preview]{left:0;top:6%;width:78%;height:23%;--tilt:-5deg}.realm-choice[data-realm=advice]{right:0;top:32%;width:71%;height:21%;--tilt:6deg}.realm-choice[data-realm=expand]{left:0;top:58%;width:76%;height:23%;--tilt:-7deg}.realm-choice[data-realm=progress]{right:0;top:84%;width:70%;height:16%;--tilt:4deg}.page-wander{opacity:.12}.leaf-diagrams{margin-top:5px}.diagram-name>svg{display:none}}
@media(max-width:360px){.diagram-name{font-size:11px;gap:4px;min-height:26px}.diagram-mark{font-size:14px}.realm-choice .drawing{height:calc(100% - 27px)}.realm-choice{padding-bottom:8px}.leaf-heading>span{font-size:11px}.realm-choice[data-realm=progress]{top:82%;height:18%}}
@media(max-height:660px) and (max-width:700px){.book-projection{top:83px;bottom:7px}.realm-caption{min-height:63px}.leaf-heading{min-height:35px}.realm-choice .drawing{height:calc(100% - 20px)}.diagram-name{font-size:10px;min-height:20px}.diagram-mark{font-size:13px}.realm-choice{padding:1px 1px 5px}}
</style>

<style scoped>
.realm-caption{flex:0 0 100px;min-height:100px}.realm-caption>div{max-width:70%}
@media(max-width:700px){.realm-caption{flex-basis:112px;min-height:112px}.realm-caption>div{max-width:none}.realm-choice[data-realm=text]{top:0;height:22%}.realm-choice[data-realm=questions]{top:26%;height:22%}.realm-choice[data-realm=notes]{top:52%;height:22%}.realm-choice[data-realm=review]{top:79%;height:20%}.realm-choice[data-realm=preview]{top:4%;height:22%}.realm-choice[data-realm=advice]{top:29%;height:20%}.realm-choice[data-realm=expand]{top:54%;height:22%}.realm-choice[data-realm=progress]{top:79%;height:20%}}
@media(max-height:660px){.realm-caption{flex-basis:66px;min-height:66px}}
</style>

<style scoped>
.returning-from-realm :deep(.realm-destination){opacity:0;transform:translateY(15px);transition:opacity .24s,transform .24s;pointer-events:none}.book-reforming .realm-spread{animation:book-reform .32s both}.book-reforming .realm-caption{animation:caption-reform .32s both}@keyframes book-reform{from{opacity:0;transform:translateY(12px) scale(.985)}to{opacity:1;transform:none}}@keyframes caption-reform{from{opacity:0}to{opacity:1}}
@media(min-width:701px){.realm-choice[data-realm=text]{left:0;top:0;width:63%;height:53%;--tilt:-5deg}.realm-choice[data-realm=questions]{right:0;top:14%;width:32%;height:33%;--tilt:9deg}.realm-choice[data-realm=notes]{left:3%;top:60%;width:45%;height:36%;--tilt:-8deg}.realm-choice[data-realm=review]{right:4%;top:63%;width:36%;height:30%;--tilt:4deg}.realm-choice[data-realm=preview]{left:0;top:8%;width:42%;height:37%;--tilt:-7deg}.realm-choice[data-realm=advice]{right:5%;top:0;width:40%;height:29%;--tilt:8deg}.realm-choice[data-realm=expand]{left:10%;top:47%;width:52%;height:50%;--tilt:-8deg}.realm-choice[data-realm=progress]{right:0;top:39%;width:32%;height:39%;--tilt:5deg}}
/* Short landscape keeps the spread usable as a scrollable sheet, with clear controls. */
@media(max-height:500px){.altar-interface{overflow-y:auto;overflow-x:hidden}.altar-nav{position:sticky;top:10px;margin:10px 3%;height:44px;left:auto;right:auto}.book-projection{position:relative;inset:auto;margin:25px 3% 20px;height:580px}.realm-spread{min-height:470px}.realm-caption{flex-basis:90px;min-height:90px}.realm-caption p{display:block}.realm-leaf{padding-top:14px}.leaf-heading{min-height:43px}.leaf-diagrams{min-height:365px}.realm-leaf::before,.realm-leaf::after{top:65px}.realm-choice .drawing{min-height:0}.realm-choice[data-realm=progress]{top:79%;height:20%}}
</style>

<style scoped>
.page-wander{opacity:.14;stroke-width:.55}.realm-choice .drawing{color:#c9dce2}.realm-choice.is-selected .drawing{color:var(--ink)}.is-selected .drawing :deep(svg){filter:drop-shadow(0 0 3px var(--ink))}.is-selected .drawing :deep(g){animation:none}
</style>

<style scoped>
/* Rotate the ink inside stable, separated hit areas. */
.realm-choice{transform:none}.realm-choice .drawing{transform:rotate(var(--tilt))}.realm-choice .diagram-name{transform:rotate(calc(var(--tilt) * .5))}.returning-from-realm :deep(.realm-destination){animation:realm-destination-out .24s both}@keyframes realm-destination-out{from{opacity:1;transform:none}to{opacity:0;transform:translateY(15px)}}
</style>
