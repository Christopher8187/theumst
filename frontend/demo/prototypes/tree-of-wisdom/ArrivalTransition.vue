<script setup lang="ts">
// One persistent scene and one progress value. Descent retraces ascent exactly.
import { shallowRef, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useWisdomI18n } from './i18n';
const {t}=useWisdomI18n();
import departure from '../../../shared/assets/between-dimensions-final.png';
const props=withDefaults(defineProps<{destination:string;direction:'up'|'down'|null;at:'home'|'tree';frameAspect?:number;imageAspect?:number}>(),{frameAspect:1672/941,imageAspect:1672/941});
const emit=defineEmits<{done:[];progress:[value:number]}>();
const progress=shallowRef(props.direction==='up'||props.at==='home'?0:1);
const ready=shallowRef(false);
let frame=0,disposed=false;
const smooth=(a:number,b:number,p:number)=>{const t=Math.max(0,Math.min(1,(p-a)/(b-a)));return t*t*(3-2*t)};
const stars=Array.from({length:100},(_,i)=>({left:`${(i*73.17+11)%100}%`,top:`${(i*37.71+3)%100}%`,width:`${i%5===0?2.5:1.2}px`,height:`${i%5===0?2.5:1.2}px`,opacity:.25+(i%5)*.12}));
const homeStyle=computed(()=>({opacity:1-smooth(.15,.47,progress.value),transform:`translate3d(0,${progress.value*36}%,0) scale(${1+progress.value*.8})`}));
const treeStyle=computed(()=>({opacity:smooth(.5,.91,progress.value),transform:`translate3d(0,${(progress.value-1)*40}%,0) scale(${1+(1-progress.value)*.88})`,'--tree-frame-ratio':props.frameAspect,'--tree-image-factor':props.imageAspect/props.frameAspect}));
const mistStyle=computed(()=>({opacity:smooth(.06,.28,progress.value)*(1-smooth(.75,.96,progress.value)),transform:`translate3d(0,${(progress.value-.5)*80}%,0)`}));
const starStyle=computed(()=>({opacity:smooth(.2,.4,progress.value)*(1-smooth(.7,.94,progress.value)),transform:`translate3d(0,${(progress.value-.5)*40}%,0)`}));
function setProgress(value:number){progress.value=value;emit('progress',value)}
function finish(){cancelAnimationFrame(frame);if(!props.direction)return;setProgress(props.direction==='up'?1:0);emit('done')}
function travel(){
  cancelAnimationFrame(frame);
  if(!ready.value||!props.direction)return;
  const start=progress.value,end=props.direction==='up'?1:0;
  const duration=window.matchMedia('(prefers-reduced-motion: reduce)').matches?180:6800*Math.abs(end-start);
  let began:number|undefined;
  function step(now:number){
    if(disposed)return;
    began??=now;
    const t=Math.min(1,(now-began)/Math.max(duration,1));
    setProgress(start+(end-start)*(t*t*(3-2*t)));
    if(t<1)frame=requestAnimationFrame(step);else emit('done');
  }
  frame=requestAnimationFrame(step);
}
watch(()=>props.direction,travel);
onMounted(async()=>{
  await Promise.all([departure,props.destination].map(src=>new Promise<void>(resolve=>{const image=new Image();image.onload=()=>resolve();image.onerror=()=>resolve();image.src=src})));
  if(disposed)return;ready.value=true;emit('progress',progress.value);travel();
});
onBeforeUnmount(()=>{disposed=true;cancelAnimationFrame(frame)});
defineExpose({finish});
</script>
<template>
  <div class="journey-stage" :class="{'in-transit':!!direction}" :data-position="progress.toFixed(3)" :aria-label="direction?(direction==='up'?t.ascending:t.descending):undefined">
    <div class="journey-space" aria-hidden="true"></div>
    <div class="journey-home" :style="homeStyle" aria-hidden="true"><img :src="departure" alt=""><div class="home-shade"></div></div>
    <div class="journey-mist" :style="mistStyle" aria-hidden="true"></div>
    <div class="journey-stars" :style="starStyle" aria-hidden="true"><i v-for="(style,i) in stars" :key="i" :style="style"></i></div>
    <div class="journey-tree" :style="treeStyle" aria-hidden="true"><img :src="destination" alt=""><div class="tree-shade"></div></div>
    <div class="journey-haze" :style="{opacity:smooth(.2,.43,progress)*(1-smooth(.6,.88,progress)),transform:`translate3d(0,${(progress-.5)*65}%,0)`}" aria-hidden="true"></div>
  </div>
</template>
<style scoped>
.journey-stage{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none;background:#162438}.journey-space{position:absolute;inset:0;background:radial-gradient(ellipse at 63% 25%,#6a4c735c,transparent 55%),radial-gradient(ellipse at 35% 85%,#759bb35e,transparent 60%),linear-gradient(#142137,#243a55 65%,#667d95)}.journey-home,.journey-tree{position:absolute;inset:0;will-change:transform,opacity;transform-origin:center}.journey-home img,.journey-tree img{height:100%;width:100%;object-fit:cover}.journey-home img{object-position:58% 45%}.journey-tree img{object-position:35% 50%}.home-shade,.tree-shade{position:absolute;inset:0}.home-shade{background:linear-gradient(0deg,#12233991,transparent 55%)}.tree-shade{background:var(--sanctuary-shade)}.journey-mist{position:absolute;inset:-75% -35%;background:radial-gradient(ellipse at 23% 28%,#bac4d18c,transparent 31%),radial-gradient(ellipse at 68% 47%,#c7b1d073,transparent 29%),radial-gradient(ellipse at 38% 71%,#849bb8b3,transparent 34%);filter:blur(35px);will-change:transform,opacity}.journey-stars{position:absolute;inset:-65% 0;will-change:transform,opacity}.journey-stars i{position:absolute;background:#f1e4db;box-shadow:0 0 6px #d0b9d2;border-radius:50%}.journey-haze{position:absolute;inset:-80% -20%;background:radial-gradient(ellipse at 56% 58%,#e3d2df5e,transparent 30%),radial-gradient(ellipse at 25% 37%,#cbdce94d,transparent 24%);filter:blur(45px);will-change:transform,opacity}@media(max-width:700px){.journey-tree img{object-position:23% 50%}}@media(prefers-reduced-motion:reduce){.journey-home,.journey-tree,.journey-mist,.journey-stars,.journey-haze{transform:none!important}.journey-mist,.journey-stars,.journey-haze{display:none}}
</style>
<style scoped>
/* Cover the original tree frame, then clip the added altar region to its right. */
.journey-tree{overflow:hidden;--tree-frame-width:max(100vw,calc(100dvh * var(--tree-frame-ratio)));--tree-focus:.35}
.journey-tree img{position:absolute;display:block;max-width:none;width:calc(var(--tree-frame-width) * var(--tree-image-factor));height:calc(var(--tree-frame-width) / var(--tree-frame-ratio));left:calc((100vw - var(--tree-frame-width)) * var(--tree-focus));top:calc((100dvh - var(--tree-frame-width) / var(--tree-frame-ratio)) * .5);object-fit:fill}
@media(max-width:700px){.journey-tree{--tree-focus:.23}}
</style>
