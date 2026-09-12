<script setup lang="ts">
// Three game-oriented grimoire selectors share the approved Sanctuary scene.
import { shallowRef, computed, onMounted, onBeforeUnmount } from 'vue';
import logo from '../../../shared/assets/logo-clear.svg';
import dawn from './assets/sacred-tree-dawn.png';
import { books } from './books';
import ProjectionVariant from './ProjectionVariant.vue';
import OrbitVariant from './OrbitVariant.vue';
import SignalVariant from './SignalVariant.vue';
import ArrivalTransition from './ArrivalTransition.vue';
import ProjectedBook from './ProjectedBook.vue';
import GrimoireReader from './GrimoireReader.vue';

type Variant = 'A' | 'B' | 'C';
const params = new URLSearchParams(location.search);
const variant = shallowRef<Variant>((['A','B','C'].includes(params.get('variant') || '') ? params.get('variant') : 'B') as Variant);
const selectedId = shallowRef(params.get('book') || 'analysis');
const search = shallowRef('');
const onlyMine = shallowRef(false);
const added = shallowRef(['analysis']);
const scene = shallowRef<'tree'|'realms'>('tree');
const readerOpen = shallowRef(false);
const place = shallowRef<'home'|'tree'>(params.get('place')==='home'?'home':'tree');
const arrival = shallowRef<InstanceType<typeof ArrivalTransition>|null>(null);
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const journey = shallowRef<'up'|'down'|null>(place.value==='tree' && params.get('arrival') !== '0' && !reducedMotion ? 'up' : null);
const journeyPosition = shallowRef(journey.value==='up'||place.value==='home'?0:1);
const treeExposure = computed(()=>Math.max(0,Math.min(1,(journeyPosition.value-.88)/.12)));
const homeExposure = computed(()=>Math.max(0,Math.min(1,(.12-journeyPosition.value)/.12)));
const shown = computed(() => books.filter(book => (!onlyMine.value || added.value.includes(book.id)) && (book.title+' '+book.subject).toLowerCase().includes(search.value.trim().toLowerCase())));
const chosenBook = computed(() => shown.value.find(book => book.id === selectedId.value) || shown.value[0]);
const hasAdded = computed(() => !!chosenBook.value && added.value.includes(chosenBook.value.id));
const variants = { A:ProjectionVariant, B:OrbitVariant, C:SignalVariant };
const names = { A:'Projection', B:'Orbit', C:'Signals' };

function updateUrl() {
  const query = new URLSearchParams(location.search);
  query.set('prototype','wisdom'); query.set('revision','3'); query.set('variant',variant.value);
  query.set('place',place.value);
  chosenBook.value ? query.set('book',chosenBook.value.id) : query.delete('book');
  history.replaceState(null,'',location.pathname+'?'+query);
}
function select(id:string) { selectedId.value=id; updateUrl(); }
function changeVariant(value:Variant) { variant.value=value; scene.value='tree'; updateUrl(); }
function cycle(step:number) {
  const options:Variant[]=['A','B','C'];
  changeVariant(options[(options.indexOf(variant.value)+step+3)%3]);
}
function add() {
  if(chosenBook.value && !hasAdded.value) added.value=[...added.value,chosenBook.value.id];
}
function journeyDone() {
  place.value=journey.value==='down'?'home':'tree';
  journey.value=null;
  updateUrl();
}
function travel(direction:'up'|'down') {
  readerOpen.value=false;
  scene.value='tree';
  journey.value=direction;
  window.scrollTo({top:0,behavior:'instant'});
}
function keydown(event:KeyboardEvent) {
  if(journey.value || readerOpen.value || place.value==='home' || (event.target as Element)?.closest('input,textarea,select,[contenteditable=true]')) return;
  if(event.key==='/') { event.preventDefault(); document.querySelector<HTMLInputElement>('[aria-label="Search grimoires"]')?.focus(); }
  if(event.key==='Escape') scene.value='tree';
  if(event.key==='ArrowLeft') { event.preventDefault(); cycle(-1); }
  if(event.key==='ArrowRight') { event.preventDefault(); cycle(1); }
}
onMounted(()=>{
  document.title='Sanctuary · Grimoire interface study';
  const icon=document.createElement('link'); icon.id='wisdom-favicon'; icon.rel='icon'; icon.href=logo; document.head.append(icon);
  window.addEventListener('keydown',keydown);
});
onBeforeUnmount(()=>{window.removeEventListener('keydown',keydown);document.getElementById('wisdom-favicon')?.remove();});
</script>

<template>
  <main class="wisdom-prototype" :class="['interface-'+variant,{'showing-realms':scene==='realms','at-home':place==='home','travelling':!!journey}]">
    <ArrivalTransition ref="arrival" :destination="dawn" :direction="journey" :at="place" @done="journeyDone" @progress="journeyPosition=$event"/>
    <div class="home-landing" :style="{opacity:homeExposure}" :inert="!!journey || place!=='home'" :aria-hidden="place!=='home'||!!journey">
      <img class="landing-logo" :src="logo" alt="Theumst">
      <div class="home-threshold"><small>THE SANCTUARY AWAITS</small><h1>Tree of Wisdom</h1><button @click="travel('up')">Ascend to the tree <span>↑</span></button><a href="https://theumst.com/">Open homepage ↗</a></div>
      <p class="landing-prototype">Journey prototype · {{names[variant]}}</p>
    </div>
    <div class="sanctuary-interface" :style="{opacity:treeExposure}" :inert="!!journey || place!=='tree'" :aria-hidden="place!=='tree'||!!journey">
      <header class="wisdom-header">
        <button class="sanctuary-brand" aria-label="Return to Tree of Wisdom" @click="scene='tree'"><img :src="logo" alt=""><span><small>THE SANCTUARY</small><strong>Tree of Wisdom</strong></span></button>
        <div class="selection-tools"><label class="grimoire-search"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/><path d="m12 12 5 5"/></svg><input v-model="search" aria-label="Search grimoires" placeholder="Search grimoires" @input="scene='tree'"><kbd>/</kbd></label><button class="my-grimoires" :aria-pressed="onlyMine" @click="onlyMine=!onlyMine;scene='tree'"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 3 8l9 4 9-4-9-4Zm-9 9 9 4 9-4M3 18l9 4 9-4"/></svg><span>{{onlyMine?'All grimoires':'My grimoires'}}</span><small>{{added.length.toString().padStart(2,'0')}}</small></button></div>
      </header>
      <div v-if="scene==='tree'">
        <component v-if="shown.length" :is="variants[variant]" :books="shown" :selected="chosenBook" :added="hasAdded" @select="select" @add="add" @enter="scene='realms'" @preview="readerOpen=true"/>
        <section v-else class="empty-grimoires"><span>⌕</span><h2>No matching grimoires</h2><p>Try another title or subject.</p><button @click="search='';onlyMine=false">Show all grimoires</button></section>
      </div>
      <section v-else-if="chosenBook" class="realm-handoff" aria-label="Next scene placeholder"><ProjectedBook :book="chosenBook" large/><small>{{chosenBook.subject}}</small><h1>{{chosenBook.title}}</h1><p>Your grimoire is ready.</p><button @click="scene='tree'">← Back to the Sanctuary</button><span>Realms will be designed in the next scene.</span></section>
      <footer class="scene-navigation"><button class="return-home" @click="travel('down')"><span>↓</span> Descend <small>Home</small></button></footer>
      <aside class="prototype-switcher" aria-label="Prototype variants"><div class="switcher-controls"><button aria-label="Previous prototype" @click="cycle(-1)">‹</button><button v-for="v in (['A','B','C'] as const)" :key="v" :aria-label="'Variant '+v+': '+names[v]" :aria-pressed="variant===v" @click="changeVariant(v)">{{v}}</button><span>{{names[variant]}}</span><button aria-label="Next prototype" @click="cycle(1)">›</button></div><p>PROTOTYPE · {{chosenBook?.short || 'No selection'}} · {{added.length}} added<span v-if="onlyMine"> · My grimoires</span><span v-if="search"> · {{search}}</span><span v-if="scene==='realms'"> · Realms next</span></p></aside>
    </div>
    <div v-if="journey" class="journey-controls"><span>{{journey==='up'?'↑ Ascending':'↓ Descending'}}</span><button @click="arrival?.finish()">Skip {{journey==='up'?'ascent':'descent'}} {{journey==='up'?'↗':'↘'}}</button></div>
    <GrimoireReader v-if="readerOpen && chosenBook" :book="chosenBook" :added="hasAdded" @close="readerOpen=false" @add="add" @enter="readerOpen=false;scene='realms'"/>
  </main>
</template>

<style>
html,body,#app{margin:0;min-width:280px;width:100%;height:100%}body{background:#192638}*{box-sizing:border-box}button,input{font:inherit}button,a{-webkit-tap-highlight-color:transparent;touch-action:manipulation}button:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid #d8b6ed;outline-offset:4px}button{cursor:pointer}.projection-content *,.orbit-details,.signal-layout{scrollbar-width:thin;scrollbar-color:#94bccd70 transparent;color-scheme:dark}.wisdom-prototype{position:relative;isolation:isolate;min-height:700px;height:100dvh;width:100%;overflow:hidden;background:#bfc6d4;color:#e3f0f6;font-family:'Bahnschrift','Segoe UI',sans-serif}.sanctuary-art{position:absolute;inset:0;overflow:hidden;z-index:-1;pointer-events:none}.sanctuary-art>img{width:100%;height:100%;object-fit:cover;object-position:35% 50%}.sanctuary-light{position:absolute;inset:0;background:linear-gradient(90deg,#14253a0a 16%,#18273b21 42%,#17233b91 100%),linear-gradient(0deg,#15283a69,transparent 25%,transparent 75%,#152c3b22)}.interface-B .sanctuary-light{background:linear-gradient(90deg,transparent 15%,#20274633 45%,#202940b3 100%),linear-gradient(0deg,#14284080,transparent 30%)}.interface-C .sanctuary-light{background:linear-gradient(90deg,transparent 40%,#15233775 100%),linear-gradient(0deg,#192d3e59,transparent 25%)}.sanctuary-mote{position:absolute;width:2px;height:2px;background:#f8e6cd;border-radius:50%;opacity:0;box-shadow:0 0 5px #e9cbdf;animation:sanctuary-drift 15s infinite ease-in-out}.sanctuary-interface{min-height:inherit;display:flow-root}.wisdom-header{position:absolute;top:0;left:0;right:0;z-index:5;padding:30px 4.5%;display:flex;justify-content:space-between;align-items:center;gap:24px}.sanctuary-brand{display:flex;align-items:center;gap:15px;background:transparent;border:0;padding:0;text-align:left;color:#344b53}.sanctuary-brand img{width:33px;height:40px;object-fit:contain}.sanctuary-brand small{display:block;font:8px 'Courier New',monospace;letter-spacing:.25em;margin:0 0 7px;color:#4d626c}.sanctuary-brand strong{font:25px/1 Georgia,serif;font-weight:400;letter-spacing:-.03em}.selection-tools{display:flex;align-items:center;gap:12px}.grimoire-search{display:flex;align-items:center;gap:11px;padding:11px 13px;border:1px solid #adcad86b;border-radius:4px 14px 4px 4px;background:#193348c9;backdrop-filter:blur(14px);color:#b5d5e4;height:42px}.grimoire-search svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.4}.grimoire-search input{width:150px;font:11px 'Bahnschrift','Segoe UI',sans-serif;background:transparent;border:0;padding:0;color:#edf4fa;outline-offset:5px}.grimoire-search input::placeholder{color:#c1d0dc}.grimoire-search kbd{font:10px 'Courier New',monospace;opacity:.6}.my-grimoires{display:flex;align-items:center;gap:10px;min-height:42px;padding:10px 13px;border:1px solid #b6bdd17a;border-radius:4px 14px 4px 4px;background:#202e45ba;backdrop-filter:blur(14px);color:#dae3ef;font:11px 'Bahnschrift','Segoe UI',sans-serif}.my-grimoires svg{width:16px;height:16px;fill:none;stroke:#cdbfe8;stroke-width:1.25}.my-grimoires small{font:9px 'Courier New',monospace;border-left:1px solid #bcb6d446;padding-left:10px;color:#bbdfe9}.my-grimoires[aria-pressed=true]{background:#2d4661ed;border-color:#bce2f2;box-shadow:inset 0 -2px 0 #c6b3eb}.scene-navigation{position:absolute;bottom:100px;left:4.5%;right:4.5%;display:flex;justify-content:space-between;align-items:center;z-index:5}.scene-navigation button{border:0;background:transparent;padding:10px 0;color:#ecedf5;font:10px 'Courier New',monospace;text-shadow:0 1px 10px #142338}.return-home{display:flex;gap:9px;align-items:center}.return-home>span{font-size:17px}.scene-coordinate{color:#d9d4e5;font-size:21px}.prototype-switcher{position:absolute;z-index:10;bottom:20px;left:50%;transform:translateX(-50%);padding:7px 12px 9px;border:1px solid #8499aa9c;background:#102336f2;color:#d8e6ef;min-width:355px;box-shadow:0 7px 20px #10203320}.switcher-controls{display:flex;align-items:center;gap:5px}.switcher-controls button{background:transparent;border:1px solid transparent;color:#a8bfce;min-width:27px;height:25px;font:11px 'Courier New',monospace}.switcher-controls button[aria-pressed=true]{color:#10273a;background:#c8dce7;border-color:#ebf4fc}.switcher-controls button:first-child,.switcher-controls button:last-child{font-size:21px}.switcher-controls>span{flex:1;text-align:center;font-size:12px;min-width:95px}.prototype-switcher>p{margin:6px 0 0;text-align:center;font:8px/1.5 'Courier New',monospace;color:#91afc0}.empty-grimoires,.realm-handoff{position:absolute;top:23%;right:6%;width:43%;padding:35px;background:#1d2f45e8;border:1px solid #aecdd15e;border-radius:4px 23px 4px 4px;backdrop-filter:blur(18px)}.empty-grimoires>span{font-size:35px;color:#c7b6e3}.empty-grimoires h2{font-size:27px;font-weight:400}.empty-grimoires p{font-size:13px;color:#becbda}.empty-grimoires button,.realm-handoff button{background:#ace5ee16;border:1px solid #a2d8e99a;color:#d9f2f7;padding:12px 16px;border-radius:4px;font-size:12px}.realm-handoff{top:18%;bottom:17%;display:flex;align-items:center;flex-direction:column;justify-content:center;text-align:center;padding:20px}.realm-handoff>small{font:9px 'Courier New',monospace;color:#b9c4df;text-transform:uppercase;margin-top:20px}.realm-handoff h1{font:30px/1.1 'Bahnschrift','Segoe UI',sans-serif;font-weight:400;max-width:20ch;margin:13px 0}.realm-handoff>p{font-size:13px;color:#b4c4d3;margin:0 0 20px}.realm-handoff>span{font:8px 'Courier New',monospace;color:#a9b6cb;margin-top:17px}@keyframes sanctuary-drift{0%,100%{opacity:0;transform:translateY(8px)}35%{opacity:.55}80%{opacity:.2;transform:translate(12px,-25px)}}@media(max-width:1000px){.wisdom-header{padding:25px 3%}.sanctuary-brand{gap:9px}.sanctuary-brand strong{font-size:21px}.grimoire-search input{width:115px}.selection-tools{gap:8px}.realm-handoff{width:57%;right:4%}}@media(max-width:700px){.wisdom-prototype{height:auto;min-height:100dvh;overflow:clip}.wisdom-header{padding:22px 20px;align-items:flex-start;flex-direction:column;gap:23px}.sanctuary-brand strong{font-size:24px}.sanctuary-brand img{width:28px;height:34px}.selection-tools{width:100%;gap:8px}.grimoire-search{flex:1;min-width:0;gap:7px;padding:10px}.grimoire-search input{min-width:0;width:100%}.grimoire-search kbd{display:none}.my-grimoires{font-size:10px;padding:10px;gap:7px}.my-grimoires small{font-size:8px;padding-left:7px}.my-grimoires svg{width:13px}.sanctuary-art>img{object-position:23% 50%}.sanctuary-light{background:linear-gradient(180deg,transparent,#1c2a4040 25%,#182b456e 80%,#182c4599)}.scene-navigation{left:22px;right:22px;bottom:92px}.scene-navigation button{font-size:9px}.prototype-switcher{width:calc(100% - 36px);min-width:0;max-width:405px;padding:7px 8px 8px;bottom:19px}.switcher-controls{gap:3px}.prototype-switcher>p{font-size:7px}.empty-grimoires,.realm-handoff{position:relative;right:auto;top:auto;bottom:auto;width:auto;margin:164px 18px 145px;padding:25px}.empty-grimoires{min-height:300px}.realm-handoff{min-height:470px}.showing-realms{min-height:790px}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}
</style>
<style>
.wisdom-prototype{background:transparent;--sanctuary-shade:linear-gradient(90deg,#14253a0a 16%,#18273b21 42%,#17233b91 100%),linear-gradient(0deg,#15283a69,transparent 25%,transparent 75%,#152c3b22)}.wisdom-prototype.interface-B{--sanctuary-shade:linear-gradient(90deg,transparent 15%,#20274633 45%,#202940b3 100%),linear-gradient(0deg,#14284080,transparent 30%)}.wisdom-prototype.interface-C{--sanctuary-shade:linear-gradient(90deg,transparent 40%,#15233775 100%),linear-gradient(0deg,#192d3e59,transparent 25%)}.sanctuary-interface[aria-hidden=true],.home-landing[aria-hidden=true]{pointer-events:none}.home-landing{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;color:#f2edf3}.landing-logo{position:absolute;top:30px;left:4.5%;width:36px}.home-threshold{text-align:center;margin-top:14vh;padding:32px;max-width:95vw;background:radial-gradient(ellipse,#13233f9c,transparent 70%)}.home-threshold small{font:9px 'Courier New',monospace;letter-spacing:.25em;color:#dfc7e1}.home-threshold h1{font:clamp(35px,5vw,66px)/1.1 Georgia,serif;font-weight:400;letter-spacing:-.03em;text-shadow:0 2px 25px #132036;margin:18px 0 30px}.home-threshold button{display:flex;align-items:center;gap:30px;margin:auto;border:1px solid #b6e3eb96;border-radius:4px 17px 4px 4px;background:#1b314ccd;backdrop-filter:blur(14px);padding:15px 22px;color:#c7f0f3;font-size:13px}.home-threshold button>span{font-size:21px}.home-threshold a{display:block;margin-top:22px;color:#e2d7e7;font:10px 'Courier New',monospace;text-decoration:none}.landing-prototype{position:absolute;bottom:24px;color:#c0ccdb;font:9px 'Courier New',monospace}.scene-navigation{position:fixed;bottom:28px;right:auto;z-index:11}.scene-navigation .return-home{padding:11px 16px;color:#d8eef3;background:#173148e8;border:1px solid #adcede6b;border-radius:4px 13px 4px 4px;backdrop-filter:blur(15px);font:12px 'Bahnschrift','Segoe UI',sans-serif;gap:12px}.return-home small{font:8px 'Courier New',monospace;color:#bcaecf;border-left:1px solid #bad0e445;padding-left:12px}.return-home:hover{background:#284760f2}.prototype-switcher{position:fixed}.journey-controls{position:fixed;z-index:60;top:24px;left:4.5%;right:4.5%;display:flex;align-items:center;justify-content:space-between;color:#f1e4ee;font:10px 'Courier New',monospace}.journey-controls button{background:#182d42a1;color:#eee8ed;border:1px solid #bdd2de5e;border-radius:4px 12px 4px 4px;padding:12px 17px;font:10px 'Courier New',monospace}.at-home,.travelling{height:100dvh;min-height:0!important;overflow:hidden!important}
@media(max-width:700px){.scene-navigation{top:19px;right:18px;left:auto;bottom:auto}.scene-navigation .return-home{min-height:38px;font-size:10px;padding:7px 10px;gap:7px}.return-home small{display:none}.return-home>span{font-size:16px}.wisdom-header{padding-top:20px}.sanctuary-brand strong{font-size:21px}.sanctuary-brand small{font-size:7px}.sanctuary-brand{gap:8px}.sanctuary-brand img{width:24px}.prototype-switcher{bottom:12px}.journey-controls{top:20px;left:20px;right:20px}.home-threshold{padding:22px}.landing-logo{top:22px;left:22px}}
</style>
<style>
@media(max-width:700px){.wisdom-prototype.interface-B{height:100dvh;min-height:650px;overflow:hidden}}
</style>
<style>
.journey-controls>span{margin-left:auto;margin-right:20px}
@media(max-width:340px){.sanctuary-brand strong{font-size:19px}.sanctuary-brand img{width:22px}.wisdom-header{padding-left:15px;padding-right:15px}.scene-navigation{right:15px}.my-grimoires{padding:9px 8px;gap:6px}.my-grimoires small{padding-left:6px}.grimoire-search{padding-left:9px;padding-right:9px}.grimoire-search input{font-size:10px}}
</style>
<style>
.journey-controls{top:auto;bottom:28px;left:auto;right:4.5%;gap:16px}.journey-controls>span{margin:0}
@media(max-width:700px){.journey-controls{top:74px;bottom:auto;left:50%;right:auto;transform:translateX(-50%);white-space:nowrap;background:#172b42b3;border-radius:4px 12px 4px 4px;padding-left:12px;gap:10px}.journey-controls button{border:0;background:transparent}}
</style>
