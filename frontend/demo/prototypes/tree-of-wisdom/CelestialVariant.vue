<script setup lang="ts">
import { shallowRef,computed } from 'vue';
import type { SampleBook } from './books';
defineProps<{books:SampleBook[];selected:string|null}>();
defineEmits<{select:[id:string]}>();
const zoom=shallowRef(1), pan=shallowRef({x:0,y:0}),dragging=shallowRef(false);
let origin={x:0,y:0,px:0,py:0};
const transform=computed(()=>`translate(${pan.value.x}px,${pan.value.y}px) scale(${zoom.value})`);
const paths:{d:string;w:number;opacity:number}[]=[];
const lights:{x:number;y:number;r:number}[]=[];
let seed=17;const random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646};
function branch(x:number,y:number,len:number,angle:number,depth:number){
 const ex=x+Math.cos(angle)*len,ey=y+Math.sin(angle)*len;
 paths.push({d:`M${x} ${y} Q${x+Math.cos(angle+.18)*len*.45} ${y+Math.sin(angle+.18)*len*.45} ${ex} ${ey}`,w:Math.max(.45,depth*.62),opacity:.22+depth*.09});
 if(depth<=0){lights.push({x:ex,y:ey,r:random()*1.9+.65});return;}
 const spread=.31+random()*.25;branch(ex,ey,len*(.69+random()*.1),angle-spread,depth-1);branch(ex,ey,len*(.67+random()*.11),angle+spread,depth-1);
}
branch(500,610,126,-Math.PI/2,7);
const positions:Record<string,object>={analysis:{left:'24%',top:'49%'},symmetry:{left:'63%',top:'25%'},light:{left:'79%',top:'54%'}};
function down(e:PointerEvent){if((e.target as Element).closest('button'))return;dragging.value=true;origin={x:e.clientX,y:e.clientY,px:pan.value.x,py:pan.value.y};(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)}
function move(e:PointerEvent){if(dragging.value)pan.value={x:Math.max(-180,Math.min(180,origin.px+e.clientX-origin.x)),y:Math.max(-90,Math.min(90,origin.py+e.clientY-origin.y))}}
function reset(){zoom.value=1;pan.value={x:0,y:0}}
</script>
<template>
 <section class="celestial" aria-label="The celestial tree">
  <header class="celestial-heading"><p>ROOTED IN WONDER</p><h1>Tree of Wisdom</h1></header>
  <div class="celestial-stage" :class="{dragging}" @pointerdown="down" @pointermove="move" @pointerup="dragging=false" @pointercancel="dragging=false">
   <div class="tree-plane" :style="{transform}">
    <svg class="star-tree" viewBox="0 0 1000 690" aria-hidden="true">
     <defs><radialGradient id="tree-aura"><stop stop-color="#e1cb9980"/><stop offset="1" stop-color="#bccdf400"/></radialGradient><filter id="tree-soft"><feGaussianBlur stdDeviation="2"/></filter></defs>
     <ellipse cx="500" cy="335" rx="290" ry="225" fill="url(#tree-aura)" opacity=".12"/>
     <g fill="none" stroke="#d8c9aa"><path v-for="(p,i) in paths" :key="i" :d="p.d" :stroke-width="p.w" :opacity="p.opacity"/></g>
     <g fill="#f6d7ac"><circle v-for="(p,i) in lights" :key="i" :cx="p.x" :cy="p.y" :r="p.r" :opacity=".35+(i%5)*.12"/></g>
     <g stroke="#cfba95" fill="none" opacity=".5"><path d="M500 604Q497 630 445 645M500 600Q507 630 555 645M500 610V665M498 621Q478 651 406 653M501 621Q529 651 593 653"/><ellipse cx="500" cy="646" rx="112" ry="18" opacity=".28"/><ellipse cx="500" cy="646" rx="164" ry="28" opacity=".12"/></g>
    </svg>
    <button v-for="book in books" :key="book.id" class="celestial-book" :class="{selected:selected===book.id}" :style="positions[book.id]" @click="$emit('select',book.id)"><span class="star-point">{{book.symbol}}</span><span class="star-label"><small>{{book.subject}}</small><strong>{{book.title}}</strong></span></button>
    <span class="root-label">THE FIRST BRANCH IS YOURS.</span>
   </div>
  </div>
  <nav class="map-controls" aria-label="Tree view controls"><button aria-label="Zoom out" @click="zoom=Math.max(.8,zoom-.1)">−</button><span>{{Math.round(zoom*100)}}%</span><button aria-label="Zoom in" @click="zoom=Math.min(1.5,zoom+.1)">+</button><button aria-label="Recenter tree" @click="reset">⌖</button></nav>
 </section>
</template>
<style scoped>
.celestial{position:absolute;inset:0;color:#e8e2d3;background:radial-gradient(ellipse at 50% 55%,#3039483b,transparent 55%)}.celestial-heading{position:absolute;top:14%;left:50%;transform:translateX(-50%);z-index:1;text-align:center;pointer-events:none;white-space:nowrap}.celestial-heading p{font:8px 'Courier New',monospace;letter-spacing:.35em;color:#c5afa2}.celestial-heading h1{font:400 clamp(35px,4vw,53px)/1.1 Georgia,serif;margin:12px 0;letter-spacing:-.035em}.celestial-stage{position:absolute;left:10%;right:10%;top:19%;bottom:9%;cursor:grab;touch-action:none;overflow:hidden}.celestial-stage.dragging{cursor:grabbing}.tree-plane{position:absolute;inset:0;transform-origin:50% 60%;transition:transform .2s ease-out;user-select:none}.dragging .tree-plane{transition:none}.star-tree{width:100%;height:100%;overflow:visible}.celestial-book{position:absolute;transform:translate(-50%,-50%);display:flex;align-items:center;gap:12px;background:transparent;border:0;color:#efeadb;text-align:left;cursor:pointer;white-space:nowrap;padding:10px}.star-point{width:41px;height:41px;display:grid;place-items:center;border:1px solid #c7b88c80;border-radius:50%;font:24px Georgia,serif;background:#152331;box-shadow:0 0 0 6px #ddc2a409,0 0 28px #eccb9415;transition:.3s}.star-label{display:block;padding:8px 10px;background:#15202edb;border-bottom:1px solid #9e998254}.star-label small{display:block;font:8px 'Courier New',monospace;color:#b9a8b6;letter-spacing:.14em;text-transform:uppercase;margin-bottom:5px}.star-label strong{font:17px Georgia,serif;display:block}.celestial-book:hover .star-point,.selected .star-point{box-shadow:0 0 0 8px #ddc2a417,0 0 34px #eccb9438;border-color:#e8d2a6;background:#3b4751}.root-label{position:absolute;bottom:3%;left:50%;transform:translateX(-50%);font:8px 'Courier New',monospace;letter-spacing:.25em;color:#a59e95;white-space:nowrap}.map-controls{position:absolute;bottom:11%;left:4%;display:flex;align-items:center;border:1px solid #71868a66;background:#152532ab}.map-controls button{border:0;background:none;color:#dbded4;width:33px;height:31px;cursor:pointer;font-size:18px}.map-controls span{font:9px 'Courier New',monospace;min-width:39px;text-align:center}.map-controls button:hover{background:#d6ceae22}@media(max-width:700px){.celestial-heading{top:16%}.celestial-stage{left:-19%;right:-19%;top:25%;bottom:15%}.star-label strong{font-size:12px}.star-label small{font-size:7px}.celestial-book{gap:5px;max-width:160px;white-space:normal}.star-label{padding:6px}.star-point{width:28px;height:28px;flex-shrink:0;font-size:18px}.root-label{font-size:7px}.map-controls{bottom:13%}}
</style>
