import { computed, onBeforeUnmount, onMounted, shallowRef, watch, type ComputedRef } from 'vue';

// Only the painted scenery moves. A small fixed overscan protects every edge.
export function useSceneParallax(paused: ComputedRef<boolean>) {
  const x=shallowRef(0), y=shallowRef(0);
  const allowed=window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
  let targetX=0,targetY=0,frame=0,last=0;
  function step(now:number) {
    const dt=last?Math.min(50,now-last):16;last=now;
    const weight=1-Math.exp(-dt/135);
    x.value+=(targetX-x.value)*weight;y.value+=(targetY-y.value)*weight;
    if(Math.abs(targetX-x.value)+Math.abs(targetY-y.value)>.025)frame=requestAnimationFrame(step);
    else{x.value=targetX;y.value=targetY;frame=0;last=0;}
  }
  function animate(){if(!frame)frame=requestAnimationFrame(step)}
  function reset(){targetX=0;targetY=0;animate()}
  function move(event:PointerEvent){
    if(!allowed.matches||paused.value||document.hidden||event.pointerType!=='mouse')return;
    targetX=Math.max(-1,Math.min(1,event.clientX/innerWidth*2-1))*Math.min(6,innerWidth*.004);
    targetY=Math.max(-1,Math.min(1,event.clientY/innerHeight*2-1))*Math.min(4,innerHeight*.004);
    animate();
  }
  function stop(){cancelAnimationFrame(frame);frame=0;last=0;targetX=targetY=0;x.value=y.value=0}
  function visibility(){if(document.hidden)stop()}
  watch(paused,value=>{if(value)reset()});
  onMounted(()=>{window.addEventListener('pointermove',move,{passive:true});window.addEventListener('blur',reset);document.documentElement.addEventListener('pointerleave',reset);document.addEventListener('visibilitychange',visibility);allowed.addEventListener('change',stop)});
  onBeforeUnmount(()=>{stop();window.removeEventListener('pointermove',move);window.removeEventListener('blur',reset);document.documentElement.removeEventListener('pointerleave',reset);document.removeEventListener('visibilitychange',visibility);allowed.removeEventListener('change',stop)});
  return {style:computed(()=>({'--scene-x':x.value+'px','--scene-y':y.value+'px'}))};
}
