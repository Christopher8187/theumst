<script setup lang="ts">
import { shallowRef, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import logo from '../../../shared/assets/logo-clear.svg';
import { sanctuaryArt } from './sceneArt';
import { books } from './books';
import { provideWisdomI18n } from './i18n';
import OrbitVariant from './OrbitVariant.vue';
import ArrivalTransition from './ArrivalTransition.vue';
import RealmBook from './RealmBook.vue';
import { realms, type RealmId } from './realms';
import { useAltarTravel } from './useAltarTravel';
import GrimoireReader from './GrimoireReader.vue';
import GrimoireCollection from './GrimoireCollection.vue';
import LanguageControl from './LanguageControl.vue';
import AcrossGrimoireActions from './AcrossGrimoireActions.vue';
const {lang,t}=provideWisdomI18n();
const params=new URLSearchParams(location.search);
const selectedId=shallowRef(params.get('book')||'analysis');
const scene=shallowRef<'tree'|'collection'|'realms'>(params.get('place')!=='home'&&params.get('view')==='realms'?'realms':params.get('view')==='collection'?'collection':'tree');
const departureScene=shallowRef<'tree'|'collection'>(scene.value==='collection'||params.get('from')==='collection'?'collection':'tree');
const altar=useAltarTravel(scene.value==='realms');
const {progress:altarPosition,moving:altarMoving,pan:altarPan,entrance:entranceExposure,book:bookExposure}=altar;
const activeRealm=shallowRef<RealmId|null>(realms.some(realm=>realm.id===params.get('realm'))?params.get('realm') as RealmId:null);
const librarySearch=shallowRef('');
const collectionSearch=shallowRef('');
const onlyMine=computed(()=>scene.value==='collection'||scene.value==='realms'&&departureScene.value==='collection');
const search=computed({get:()=>onlyMine.value?collectionSearch.value:librarySearch.value,set:value=>{if(onlyMine.value)collectionSearch.value=value;else {librarySearch.value=value;if(scene.value==='realms')goTree()}}});
const sampleBooks=shallowRef(params.get('scenario')==='empty-library'?[]:books.map(book=>({...book,completed:params.get('scenario')==='progress'?(book.id==='analysis'?12:book.id==='symmetry'?2:0):0})));
const added=shallowRef(params.get('scenario')==='empty-collection'?[]:['analysis']);
const toast=shallowRef('');
let toastTimer:ReturnType<typeof setTimeout>|undefined;
const place=shallowRef<'home'|'tree'>(params.get('place')==='home'?'home':'tree');
const arrival=shallowRef<InstanceType<typeof ArrivalTransition>|null>(null);
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const journey=shallowRef<'up'|'down'|null>(scene.value!=='realms'&&place.value==='tree'&&params.get('arrival')!=='0'&&!reducedMotion?'up':null);
const readerOpen=shallowRef(scene.value!=='realms'&&!journey.value&&place.value==='tree'&&params.get('panel')==='brief');
const journeyPosition=shallowRef(journey.value==='up'||place.value==='home'?0:1);
const treeExposure=computed(()=>Math.max(0,Math.min(1,(journeyPosition.value-.88)/.12)));
const homeExposure=computed(()=>Math.max(0,Math.min(1,(.12-journeyPosition.value)/.12)));
const shown=computed(()=>{
  const result=sampleBooks.value.filter(book=>(!onlyMine.value||added.value.includes(book.id))&&(book.title+' '+book.subject).toLowerCase().includes(search.value.trim().toLowerCase()));
  return onlyMine.value?result.sort((a,b)=>added.value.indexOf(a.id)-added.value.indexOf(b.id)):result;
});
const chosenBook=computed(()=>sampleBooks.value.find(book=>book.id===selectedId.value)||shown.value[0]);
const collectionTotal=computed(()=>sampleBooks.value.filter(book=>added.value.includes(book.id)).length);
const hasAdded=computed(()=>!!chosenBook.value&&added.value.includes(chosenBook.value.id));
function updateUrl(){
  const query=new URLSearchParams(location.search);
  query.set('prototype','wisdom');query.set('revision','7');query.delete('variant');query.delete('brief');query.delete('actions');query.set('place',place.value);query.set('view',scene.value);
  scene.value==='realms'&&activeRealm.value?query.set('realm',activeRealm.value):query.delete('realm');
  scene.value==='realms'&&departureScene.value==='collection'?query.set('from','collection'):query.delete('from');
  readerOpen.value?query.set('panel','brief'):query.delete('panel');
  chosenBook.value?query.set('book',chosenBook.value.id):query.delete('book');
  history.replaceState(null,'',location.pathname+'?'+query);
}
function select(id:string){selectedId.value=id;updateUrl()}
function goTree(){
  if(altarMoving.value)return;
  readerOpen.value=false;
  if(scene.value==='realms'){
    altar.travel(0,async()=>{scene.value=departureScene.value;activeRealm.value=null;updateUrl();await nextTick();document.querySelector<HTMLButtonElement>(scene.value==='collection'?'.personal-actions button:last-child':'.orbit-details .summon-action')?.focus({preventScroll:true})});
  }else{scene.value='tree';updateUrl()}
}
function toggleCollection(){readerOpen.value=false;scene.value=onlyMine.value?'tree':'collection';updateUrl()}
function openBrief(id:string){select(id);readerOpen.value=true}
function add(){if(chosenBook.value&&!hasAdded.value)added.value=[chosenBook.value.id,...added.value]}
async function remove(id:string){
  // Collection membership is independent of checked-off knowledge and progress.
  const position=shown.value.findIndex(book=>book.id===id);
  const focusId=shown.value[position+1]?.id||shown.value[position-1]?.id;
  added.value=added.value.filter(value=>value!==id);
  toast.value=t.value.removedGrimoire+' '+t.value.removalKeepsPalace;
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.value='',3600);
  await nextTick();(document.querySelector<HTMLButtonElement>(`.remove-grimoire[data-book="${focusId}"]`)||document.querySelector<HTMLButtonElement>('.personal-grimoires header button'))?.focus({preventScroll:true});
}
function enter(id=chosenBook.value?.id){if(!id||altarMoving.value)return;select(id);added.value=[id,...added.value.filter(value=>value!==id)];readerOpen.value=false;activeRealm.value=null;departureScene.value=onlyMine.value?'collection':'tree';scene.value='realms';updateUrl();altar.travel(1)}
function changeRealm(value:RealmId|null){activeRealm.value=value;updateUrl()}
function notifySoon(id:string){toast.value=t.value[id]+' · '+t.value.acrossGrimoires+' · '+t.value.comingSoon;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.value='',3200)}
function journeyDone(){place.value=journey.value==='down'?'home':'tree';journey.value=null;updateUrl()}
function travel(direction:'up'|'down'){readerOpen.value=false;scene.value='tree';journey.value=direction;window.scrollTo({top:0,behavior:'instant'})}
function keydown(event:KeyboardEvent){
  if(journey.value||altarMoving.value||scene.value==='realms'||readerOpen.value||place.value==='home'||(event.target as Element)?.closest('input,textarea,select,[contenteditable=true],.across-group'))return;
  if(event.key==='/'){event.preventDefault();document.querySelector<HTMLInputElement>('.grimoire-search input')?.focus()}
  if(event.key==='Escape')goTree();
}
watch(shown,list=>{if(scene.value==='tree'&&list.length&&!list.some(book=>book.id===selectedId.value)){selectedId.value=list[0].id;updateUrl()}},{immediate:true});
watch(lang,()=>{document.title='Theumst · '+t.value.brief});
watch(readerOpen,updateUrl);
onMounted(()=>{document.title='Theumst · '+t.value.brief;const icon=document.createElement('link');icon.id='wisdom-favicon';icon.rel='icon';icon.href=logo;document.head.append(icon);window.addEventListener('keydown',keydown);updateUrl()});
onBeforeUnmount(()=>{clearTimeout(toastTimer);window.removeEventListener('keydown',keydown);document.getElementById('wisdom-favicon')?.remove()});
</script>
<template>
  <main class="wisdom-prototype interface-B actions-E chosen-folio" :class="{'brief-open':readerOpen,'showing-realms':scene==='realms','showing-collection':onlyMine,'at-home':place==='home','travelling':!!journey}" :data-altar-position="altarPosition.toFixed(3)">
    <ArrivalTransition ref="arrival" :destination="sanctuaryArt.source" :frame-aspect="sanctuaryArt.frameAspect" :image-aspect="sanctuaryArt.imageAspect" :altar-pan="altarPan" :direction="journey" :at="place" @done="journeyDone" @progress="journeyPosition=$event"/>
    <div class="home-landing" :style="{opacity:homeExposure}" :inert="!!journey||place!=='home'" :aria-hidden="place!=='home'||!!journey"><img class="landing-logo" :src="logo" alt="Theumst"><div class="home-threshold"><button @click="travel('up')">{{t.ascend}} <span>↑</span></button><a href="https://theumst.com/">{{t.openHomepage}} ↗</a></div></div>
    <div class="sanctuary-interface" :style="{opacity:treeExposure*entranceExposure}" :inert="!!journey||place!=='tree'||scene==='realms'" :aria-hidden="place!=='tree'||!!journey||scene==='realms'">
      <header class="wisdom-header"><button class="sanctuary-brand" :aria-label="t.allGrimoires" @click="goTree"><img :src="logo" alt="Theumst"></button><div class="selection-tools"><label class="grimoire-search"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/><path d="m12 12 5 5"/></svg><input v-model="search" :aria-label="onlyMine?t.searchGrimoires:t.search" :placeholder="onlyMine?t.searchGrimoires:t.search"><kbd>/</kbd></label><LanguageControl/></div></header>
      <div v-if="!onlyMine"><OrbitVariant v-if="shown.length" :books="shown" :selected="chosenBook" :added="hasAdded" @select="select" @add="add" @enter="enter()" @preview="readerOpen=true"/><section v-else class="empty-grimoires"><span>⌕</span><h2>{{search.trim()?t.noMatches:t.libraryUnavailable}}</h2><p v-if="search.trim()">{{t.trySearch}}</p><button v-if="search.trim()" @click="search=''">{{t.clearSearch}}</button></section></div>
      <GrimoireCollection v-else-if="onlyMine" :books="shown" :total="collectionTotal" :query="collectionSearch" @brief="openBrief" @enter="enter" @remove="remove" @back="goTree" @clear="collectionSearch=''"/>
      <footer class="scene-navigation"><button class="return-home" @click="travel('down')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v16m-6-6 6 6 6-6"/></svg>{{t.descend}}</button></footer>
      <AcrossGrimoireActions :count="collectionTotal" :collection-active="onlyMine" @collection="toggleCollection" @action="notifySoon"/>

    </div>
    <RealmBook v-if="scene==='realms'&&chosenBook" :key="chosenBook.id" :book="chosenBook" :initial-realm="activeRealm||undefined" :reveal="bookExposure" :ready="!altarMoving&&altarPosition===1" @back="goTree" @realm="changeRealm"/>
    <div v-if="altarMoving" class="altar-travel-controls"><button @click="altar.finish()">{{t.realmSkip}} ↗</button></div>
    <div v-if="journey" class="journey-controls"><span>{{journey==='up'?'↑ '+t.ascending:'↓ '+t.descending}}</span><button @click="arrival?.finish()">{{journey==='up'?t.skipAscent:t.skipDescent}} {{journey==='up'?'↗':'↘'}}</button></div>
    <GrimoireReader v-if="readerOpen&&chosenBook" :key="chosenBook.id" :book="chosenBook" :added="hasAdded" @close="readerOpen=false" @add="add" @enter="enter()"/>
    <div v-if="toast" class="wisdom-toast" role="status">{{toast}}</div>
  </main>
</template>
<style>
.brief-C-open .across-group{opacity:0;pointer-events:none}
</style>
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
<style>
.wisdom-language{display:flex;align-items:center;gap:7px;border:1px solid #c4ccdf50;border-radius:4px 12px 4px 4px;background:#203549d9;color:#d5d3e6;padding:0 10px;min-height:42px}.wisdom-language>span{font-size:12px}.wisdom-language select{font-size:10px;color:#dfebf2;background:transparent;border:0;max-width:77px;padding:8px 0;cursor:pointer}.wisdom-language option{color:#e7edf4;background:#203549}.scene-navigation{gap:12px}.entrance-tools{position:relative}.entrance-tools>button{padding:12px!important;font-size:10px!important;border:1px solid #b5c7df42!important;background:#183149c7!important;border-radius:4px;color:#cad1e3!important}.entrance-tools-menu{position:absolute;left:0;bottom:calc(100% + 8px);width:135px;padding:6px;background:#1d3048f5;border:1px solid #a4cbd270;border-radius:4px 13px 4px 4px;box-shadow:0 10px 30px #0e22356b}.entrance-tools-menu>button{display:block;width:100%;text-align:left;padding:12px!important;font-size:11px!important;min-height:38px}.entrance-tools-menu>button:hover{background:#a8d9eb17}.wisdom-toast{position:fixed;bottom:105px;left:50%;transform:translateX(-50%);z-index:80;background:#1d354bee;border:1px solid #accad568;color:#e5e5f1;border-radius:5px;padding:15px 22px;font:12px 'Segoe UI',sans-serif;max-width:90vw}.realm-collection{margin-top:10px}
@media(max-width:1000px){.grimoire-search input{width:100px}.wisdom-language{padding:0 7px}.wisdom-language select{max-width:65px}}
@media(max-width:700px){.wisdom-language{padding:0 6px;gap:4px}.wisdom-language>span{display:none}.wisdom-language select{width:57px;max-width:57px;font-size:9px}.my-grimoires{gap:6px;font-size:9px;padding:9px 8px}.my-grimoires svg{display:none}.my-grimoires small{font-size:7px;padding-left:6px}.grimoire-search input{font-size:10px;width:100%}.selection-tools{gap:6px}.scene-navigation{gap:6px}.entrance-tools>button{padding:8px!important;min-height:38px}.scene-navigation .return-home{padding:7px 9px}.entrance-tools-menu{bottom:auto;top:calc(100% + 8px);left:auto;right:0}.sanctuary-brand strong{font-size:20px}.wisdom-header{padding-left:16px;padding-right:16px}.sanctuary-brand img{width:21px}.sanctuary-brand{gap:6px}.scene-navigation{right:16px}.wisdom-prototype.showing-collection{height:100dvh;min-height:650px}.showing-realms .realm-handoff{margin-top:145px;min-height:0;height:calc(100dvh - 242px)}.showing-realms .realm-handoff>.projected-book{transform:scale(.65);margin:-36px 0}.showing-realms .realm-handoff h1{font-size:24px}.showing-realms .realm-handoff>span{font-size:8px;line-height:1.5}}
@media(max-width:340px){.sanctuary-brand strong{font-size:17px}.sanctuary-brand small{font-size:6px}.sanctuary-brand img{width:19px}.scene-navigation .return-home{font-size:9px;padding:7px}.entrance-tools>button{font-size:9px!important;padding:7px!important}.my-grimoires{font-size:8px}.my-grimoires small{display:none}.wisdom-language select{width:51px}.grimoire-search svg{width:12px}.grimoire-search{gap:5px;padding:9px 7px}.grimoire-search input{font-size:9px}}
</style>
<style>
/* Round 5 compares Brief structure and navigation placement; the book chooser stays Orbit. */
.wisdom-header{padding-top:25px}.sanctuary-brand img{width:38px;height:45px}.actions-D .selection-tools{margin-right:115px}.scene-navigation{right:auto;bottom:25px}.scene-navigation .return-home{padding:11px 15px}.orbit-detail-line{margin-bottom:18px;opacity:.55}.orbit-details .detail-heading h2{margin-top:0}.actions-F .orbit-layout{top:14%;bottom:225px}.actions-F .orbital-books{height:235px}.actions-F .personal-grimoires{bottom:235px}.actions-F .realm-handoff{height:calc(100dvh - 350px)}.wisdom-toast{bottom:100px;max-width:min(550px,calc(100vw - 30px));font-size:12px;line-height:1.6}.wisdom-language select{font-size:11px}.actions-F .scene-navigation{bottom:115px}
@media(max-width:700px){.wisdom-header{padding:18px 16px;gap:19px}.sanctuary-brand{align-self:flex-start}.sanctuary-brand img{width:32px;height:39px}.selection-tools{width:100%;gap:10px}.actions-D .selection-tools{margin-right:0}.grimoire-search{flex:1}.grimoire-search input{width:100%;font-size:12px}.wisdom-language select{width:73px;font-size:11px}.scene-navigation,.actions-F .scene-navigation{position:fixed;top:18px;bottom:auto;left:70px;right:auto}.scene-navigation .return-home{min-height:39px;font-size:11px;padding:9px 12px}.orbit-layout{top:139px;bottom:106px}.actions-E .orbit-layout{top:235px}.actions-E .orbital-books{height:155px}.actions-F .orbit-layout{top:139px;bottom:215px}.actions-F .orbital-books{height:157px}.actions-F .orbit-details{margin-top:8px;padding-bottom:14px}.actions-E .orbit-details{margin-top:8px}.actions-F .orbit-details .grimoire-summary,.actions-E .orbit-details .grimoire-summary{font-size:12px;line-height:1.55;margin-bottom:13px}.actions-E .personal-grimoires{top:245px;bottom:105px}.actions-F .personal-grimoires{top:144px;bottom:225px}.orbit-detail-line{margin-bottom:16px}.actions-F .realm-handoff{height:calc(100dvh - 350px)}.wisdom-toast{top:75px;bottom:auto;z-index:25}}
</style>
<style>
.brief-C-open .orbit-details{opacity:0;pointer-events:none}.brief-C-open .orbital-books{opacity:.5}.actions-F .wisdom-toast{bottom:224px}@media(max-width:700px){.actions-F .wisdom-toast{top:75px;bottom:auto}}
</style>

<style>
/* One selected folio and rail, with no comparison controls. */
.chosen-folio .wisdom-header{gap:20px}.chosen-folio .grimoire-search{height:44px}.chosen-folio .selection-tools{margin-right:0;gap:12px}.chosen-folio .return-home svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.35;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}.chosen-folio .orbit-layout{bottom:10%}.chosen-folio .personal-grimoires{bottom:70px}.chosen-folio .wisdom-toast{bottom:28px}.brief-open .across-group,.brief-open .wisdom-header,.brief-open .scene-navigation,.brief-open .orbit-details{opacity:0;pointer-events:none}.brief-open .orbital-books{opacity:.25}
@media(max-width:700px){.chosen-folio .wisdom-header{padding-top:calc(18px + env(safe-area-inset-top))}.chosen-folio .selection-tools{gap:9px}.chosen-folio .grimoire-search{min-width:0;padding-inline:10px;gap:8px}.chosen-folio .grimoire-search input{min-width:0;font-size:12px}.chosen-folio .grimoire-search svg{width:15px;height:15px;flex-shrink:0}.chosen-folio .grimoire-search kbd{display:none}.chosen-folio .scene-navigation{top:calc(18px + env(safe-area-inset-top))}.chosen-folio .orbit-layout{top:calc(236px + env(safe-area-inset-top));bottom:max(26px,calc(16px + env(safe-area-inset-bottom)))}.chosen-folio .orbital-books{height:clamp(150px,22dvh,182px)}.chosen-folio .personal-grimoires{top:calc(238px + env(safe-area-inset-top));bottom:max(25px,env(safe-area-inset-bottom))}.chosen-folio .wisdom-toast{top:auto;bottom:max(22px,env(safe-area-inset-bottom))}.chosen-folio .realm-handoff{height:calc(100dvh - 290px);margin-top:250px}}
</style>

<style>
/* Round 7 reveals the altar without swapping or resizing the existing scene. */
.wisdom-prototype.showing-realms{height:100dvh;min-height:0;overflow:hidden}.altar-travel-controls{position:fixed;z-index:65;bottom:25px;right:4.5%}.altar-travel-controls button{min-height:44px;padding:10px 15px;background:#1b334abf;backdrop-filter:blur(10px);border:1px solid #b5cfde65;color:#e1edf0;font:11px 'Bahnschrift','Segoe UI',sans-serif}.showing-realms .wisdom-toast{display:none}
</style>
