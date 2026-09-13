import { computed, onBeforeUnmount, shallowRef, watch, type ComputedRef } from 'vue';

// A continuous angle lets rapid selections reverse from their current position.
export function useOrbitMotion(selection: ComputedRef<number>, count: ComputedRef<number>) {
  const spacing=(total:number)=>total===2?120:360/Math.max(1,total);
  const phase = shallowRef(selection.value * spacing(count.value));
  let frame = 0;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  function settle() { cancelAnimationFrame(frame); phase.value = selection.value * spacing(count.value); }
  watch([selection,count], ([position,total],[,oldTotal]) => {
    cancelAnimationFrame(frame);
    const target = position * spacing(total);
    if(total !== oldTotal || reduced.matches) { phase.value=target; return; }
    const start=phase.value, delta=((target-start+540)%360+360)%360-180;
    let began:number|undefined;
    function step(now:number) {
      began??=now;
      const p=Math.min(1,(now-began)/820), eased=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
      phase.value=start+delta*eased;
      if(p<1)frame=requestAnimationFrame(step);
    }
    frame=requestAnimationFrame(step);
  });
  reduced.addEventListener('change',settle);
  onBeforeUnmount(()=>{cancelAnimationFrame(frame);reduced.removeEventListener('change',settle)});
  const positions=computed(()=>Array.from({length:count.value},(_,i)=>{
    const angle=(i*spacing(count.value)-phase.value)*Math.PI/180, depth=Math.cos(angle);
    return {'--arc-x':Math.sin(angle),'--arc-y':(1-depth)*11+'px','--arc-z':(depth-1)*76+'px','--cover-y':Math.sin(angle)*-19-12+'deg','--cover-z':Math.sin(angle)*-3+'deg','--book-presence':.69+(depth+1)*.155,zIndex:Math.round((depth+1)*10)};
  }));
  return {positions};
}
