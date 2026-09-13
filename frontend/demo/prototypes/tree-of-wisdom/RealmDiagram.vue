<script setup lang="ts">
import type { RealmId } from './realms';
defineProps<{ kind: RealmId }>();

// Drawn as small scientific plates: pressure, structure, then selective shading.
const spiralPoint = (t: number) => {
  const r = 3 * Math.exp(t * .17), a = t - 1.15;
  return [105 + Math.cos(a) * r, 82 + Math.sin(a) * r * .86];
};
const spiral = Array.from({length:190},(_,i)=>{const [x,y]=spiralPoint(i/10);return `${i?'L':'M'}${x.toFixed(2)} ${y.toFixed(2)}`}).join(' ');
const chambers = Array.from({length:24},(_,i)=>{
  const t=7.1+i*.49,a=spiralPoint(t),b=spiralPoint(t-Math.PI*2),c=spiralPoint(t-.7);
  return `M${a[0]} ${a[1]} Q${c[0]} ${c[1]} ${b[0]} ${b[1]}`;
});
const stairPoint=(i:number,r:number,angle=0,drop=0)=>{const a=-.6+i*.24+angle;return [112+Math.cos(a)*r,136-i*8+Math.sin(a)*r*.31+drop]};
const line=(p:number[])=>p.map(v=>v.toFixed(2)).join(' ');
const stairs=Array.from({length:12},(_,i)=>{
  const a=stairPoint(i,20),b=stairPoint(i,58),c=stairPoint(i,58,.21),d=stairPoint(i,20,.21);
  return {top:`M${line(a)} L${line(b)} L${line(c)} L${line(d)}Z`,edge:`M${line(b)}v4L${line([c[0],c[1]+4])}L${line(c)}`,rail:`M${line(stairPoint(i,58,.12))}v-14`};
});
const rail=stairs.map((_,i)=>`${i?'L':'M'}${line(stairPoint(i,58,.12,-14))}`).join(' ');
</script>

<template>
  <svg class="realm-diagram" viewBox="0 0 220 165" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
    <g v-if="kind==='text'">
      <path class="setting-soft" d="M12 50q22-10 43-5 18-13 42-5 28-18 55-9 20-10 49-6M16 55q29 0 50 8m111-25q16 0 28 7"/>
      <path class="construction" d="M18 137q83 25 184-12M108 30v115m-70-5 7 9m138-10 7 7"/>
      <path class="contour" d="M32 62q39-14 74 15 34-29 81-31l-10 72q-41 0-70 26-39-26-76-8l1-74Z"/>
      <path class="contour" d="M33 58q39-19 73 16 24-32 58-43l13 17M106 74q-3 32 1 66M35 56q38-27 62-28l8 42"/>
      <path class="detail" d="M39 57q31-19 55-23l9 34M38 62q27-11 58 9m-57 2q26-10 57 9m-57 3q29-8 56 11m-56 0q29-7 57 11m-56 0q26-7 57 11M118 79q26-24 51-29m-50 40q27-24 53-28m-54 38q26-23 52-27m-50 36q27-23 49-26m-46 33q23-19 45-23"/>
      <path class="detail" d="M28 68l-3 74q43-15 82 8 39-28 72-27l13-70M29 145q41-12 77 8m4-2q35-23 67-24m-75-8 1 20m6-14 1 16"/>
      <path class="hatching" d="m39 131 5 6m2-8 6 6m1-9 6 7m2-7 6 6m2-7 6 7m4-6 5 7m4-4 5 8m3-6 5 8m15-11 4 8m3-12 4 8m4-14 4 8m4-13 4 7m4-13 4 7m4-12 4 7m4-12 4 7m5-9 4 5"/>
      <path class="detail" d="M150 36q8-15 20-20l-9 25M70 42q-8-10-5-21" opacity=".55"/>
    </g>
    <g v-else-if="kind==='questions'">
      <path class="setting-soft" d="M18 141C28 58 68 13 112 12c45-1 84 46 92 124M30 140C42 73 73 34 111 30"/>
      <ellipse class="construction" cx="112" cy="88" rx="76" ry="55" transform="rotate(-22 112 88)" stroke-dasharray="28 5 2 5"/>
      <path class="construction" d="m42 111 143-54M113 18l-3 128M41 135l136-8m-129 9 1-7m124 1-1-7"/>
      <path class="contour" d="m107 30 49 22 17 48-40 34-60-13-21-48 55-43Z"/>
      <path class="detail" d="m107 30 1 46 48-24m-104 21 56 3 65 24m-100 21 35-45 25 58M52 73l37-20 18-23m1 46 28 18 37 6M73 121l18-21 42 34"/>
      <path class="construction" d="m89 53 47 41-45 6-2-47m67-1-20 42" stroke-dasharray="3 4"/>
      <path class="shade" d="m52 73 56 3-35 45Z"/>
      <path class="hatching" d="m56 78 9 15m-5-15 12 21m-8-20 11 21m-6-20 12 20m-7-19 11 18m-6-17 10 14m-5-13 8 10m-3-9 7 8m-39-3 14 25m-7-24 12 20m-7-18 10 15m-5-13 7 9M140 102l17 5m-20 1 15 5m-20 0 14 5m-15 0 9 4"/>
      <path class="detail" d="M30 86q0-39 38-53m-8-1 8 1-4 7" opacity=".55"/>
      <path class="setting" d="M43 140q51 17 120 6 18-3 31-11M57 146q47 9 101 1"/>
      <circle class="detail" cx="108" cy="76" r="2.3"/>
    </g>
    <g v-else-if="kind==='notes'">
      <path class="setting-soft" d="m15 116 110-17 75 27-109 34-76-44Zm76 44 2-9 18 4"/>
      <path class="construction" d="M24 148q91-6 167-29M60 145l113-126"/>
      <path class="contour" d="M53 147C89 104 130 51 183 17c-2 30-14 55-30 68-22 18-54 22-70 42M179 20C144 20 117 43 104 65l3 2-7 5c-10 17-13 30-27 51"/>
      <path class="detail" d="M58 141C98 98 138 49 179 22M77 121q-1-17 12-34M86 111q-1-17 12-33M94 101q0-18 16-35M105 86q3-10 11-22M113 80q2-18 17-32M122 69q4-17 18-30M132 58q6-16 18-23M143 46q9-14 18-17M78 124q35-6 54-21M87 113q39-7 55-22M96 103q40-8 55-26M105 92q39-7 54-28M114 81q37-9 48-25M124 70q25-7 34-20M134 58q28-8 36-22M145 46q22-7 27-17"/>
      <path class="hatching" d="M92 92l-7 22m13-31-6 22m12-31-5 22m13-31-6 22m14-31-6 22m14-30-6 18m14-24-6 14M96 109l26-7m-18-11 29-8m-20-2 27-9m-19-2 28-11m-16 0 22-11m-13 1 17-10"/>
      <path class="contour" d="m54 147-9 7 5-11 4 4Z"/>
      <path class="detail" d="M44 153c-37 9-30-12-5-8s31 12 57 4M122 137q20-8 43-9"/>
      <path class="construction" d="m126 144 37-8m-126-24 23 2m-30 5 25 1"/>
    </g>
    <g v-else-if="kind==='review'">
      <path class="setting-soft" d="M10 139q28-14 56-2 22 10 50 1 30-11 91 1M16 149q25-9 47-1m73-2q29-8 58 1"/>
      <path class="contour" :d="spiral"/>
      <path v-for="(chamber,i) in chambers" :key="i" :d="chamber" class="detail" :opacity=".5+(i%3)*.13"/>
      <path class="construction" d="M33 124q-13-65 38-96m-38 96 8 11m16-4q64 32 123-11M104 8v12m-59 59H31m73 70v9"/>
      <path class="hatching" d="m126 126-3 6m9-8-2 8m8-11-1 8m7-12v7m6-12 1 7m4-13 2 7m3-12 3 5m1-13 4 5m-1-13 4 4m-2-11 4 3"/>
      <path class="detail" d="M171 60q16 27 1 47" opacity=".45"/>
    </g>
    <g v-else-if="kind==='preview'">
      <g class="setting">
        <circle cx="30" cy="38" r="9"/><path d="M26 30q10 8 1 16"/>
        <ellipse cx="190" cy="124" rx="11" ry="5" transform="rotate(-18 190 124)"/><path d="M179 128q13 9 26-1"/>
      </g>
      <ellipse class="construction" cx="111" cy="83" rx="93" ry="30" transform="rotate(-24 111 83)"/>
      <ellipse class="detail" cx="111" cy="83" rx="65" ry="52" transform="rotate(-24 111 83)"/>
      <ellipse class="contour" cx="111" cy="83" rx="43" ry="53" transform="rotate(-24 111 83)"/>
      <ellipse class="detail" cx="111" cy="83" rx="35" ry="45" transform="rotate(-24 111 83)"/>
      <path class="contour" d="M102 51c-28 25-17 49 10 56-38 3-54-39-10-56Z"/>
      <path class="shade" d="M102 51c-28 25-17 49 10 56-38 3-54-39-10-56Z"/>
      <path class="detail" d="m77 30-5-9m9 7-2-7m7 5-1-6m33 120 3 8m3-11 2 6m4-9 3 6M46 94l-10 4m144-33 9-4"/>
      <path class="construction" d="m88 18 47 138M24 119 195 47m-38-27 13 19 19 5m-32-24-4 24 17-5"/>
      <circle class="detail" cx="157" cy="20" r="2"/><circle class="detail" cx="170" cy="39" r="1.5"/><circle class="detail" cx="189" cy="44" r="2"/>
      <path class="hatching" d="m79 72 5 1m-6 5 5 1m-4 5 5 1m-3 5 5 1m-3 4 5 1m-1 4 5 1m0 3 5 1"/>
    </g>
    <g v-else-if="kind==='advice'">
      <path class="setting-soft" d="M28 112V41q0-17 17-17h105q18 0 18 17v71M12 129l175-24 26 18-171 37-30-31Z"/>
      <path class="construction" d="m70 72-43 59m72-45 41 59"/>
      <ellipse class="detail" cx="79" cy="137" rx="56" ry="10" transform="rotate(-5 79 137)"/>
      <path class="construction" d="M34 140q46 16 94-7m-87 12q46 11 79-6"/>
      <path class="contour" d="M144 133c-21-23-1-48 0-70s-9-35-25-33M139 132c-21-26 2-50 1-70s-8-29-20-28"/>
      <path class="contour" d="M119 29c-19-17-34-10-46 5l-17 32 47 25 17-33q9-18-1-29Z"/>
      <ellipse class="contour" cx="80" cy="79" rx="27" ry="7" transform="rotate(28 80 79)"/>
      <ellipse class="detail" cx="80" cy="79" rx="21" ry="4" transform="rotate(28 80 79)"/>
      <path class="detail" d="M74 35q23 6 39 25M81 29q23 3 36 24M94 24q15 4 24 15"/>
      <path class="hatching" d="m101 35 13 11m-17-7 16 14m-20-10 18 14m-22-10 19 14m-23-10 21 14m-26-9 23 13m-27-8 24 13"/>
      <ellipse class="contour" cx="146" cy="139" rx="30" ry="7"/><path class="detail" d="M116 140v4q31 13 60-1v-4m-40-4q7-5 17 0m-9-7v8"/>
      <path class="hatching" d="m125 142 2 5m5-4 2 6m5-6 1 6m6-6v6m6-7-1 6m7-8-1 6m6-7-1 5"/>
    </g>
    <g v-else-if="kind==='expand'">
      <path class="setting" d="M12 145q31-17 63 1 30 15 66-2 31-14 68 0M73 147q-18 2-31 14m34-13q10 6 20 15m-23-13q-2 8-10 14"/>
      <path class="contour" d="M69 152c29-42 39-91 63-133M75 149c24-40 35-87 55-125"/>
      <path class="contour" d="M93 106C62 103 44 82 43 57c34 5 56 24 50 49Zm16-35c-27-5-40-24-36-43 24 3 40 19 36 43Zm12-26c-5-30 8-40 22-41 4 24-5 36-22 41ZM101 89c7-27 26-42 51-37-6 28-25 35-51 37Zm-16 37c19-33 41-36 66-23-18 20-35 28-66 23Z"/>
      <path class="detail" d="m44 59 49 47m-12-13-20-6m15 0-8-20m14 29-23-3m8-14-13-4m34 23-5-22M74 30l35 41m-10-14-15-6m11 1-4-17m11 29-17-4M122 44l19-38m-13 25 10-5m-5-5-4-9M102 88l48-34m-35 25 9-19m0 13 15-3m-9-1 7-14M87 125l61-20m-42 14 16-14m-6 12 15 3m-1-8 10-5"/>
      <path class="hatching" d="m58 70 9 14m-3-9 10 15m-3-9 10 14m-3-8 9 12m-5-6 8 10M89 46l7 12m-2-6 8 11m-3-7 7 11M111 83l12-3m-4-3 13-3m-4-3 11-3M100 123l16 1m-7-4 15 1m-6-5 14 1"/>
      <path class="construction" d="M55 156q42-7 66-2m-60-29-17 7m111-47 22-6"/>
    </g>
    <g v-else>
      <path class="setting-soft" d="M106 41 21 147m99-111 83 100M21 147l45 13m137-24-44 25"/>
      <path class="setting" d="M94 46V18l40-4 16 14v31M94 18l19 11 37-1m-51 15 22-7 18 6-24 8-16-7Z"/>
      <path class="construction" d="M112 18v140M34 153q80 19 151-9m-83-128 22-4"/>
      <g v-for="(step,i) in stairs" :key="i"><path :d="step.top" class="detail"/><path :d="step.edge" class="contour"/><path v-if="i%3===0" :d="step.rail" class="detail"/></g>
      <path :d="rail" class="contour"/>
      <path class="detail" d="M104 142V38m4 101V35m-6 6 18-7"/>
      <path class="hatching" d="m137 118 9 3m-12-11 10 3m-16-9 12 3m-19-9 13 3m-23-9 14 3m-25-9 14 3m-28-8 15 3"/>
      <path class="construction" d="M49 124q-25-28-1-51m-5 4 5-4 1 6"/>
    </g>
  </svg>
</template>

<style scoped>
.realm-diagram{display:block;width:100%;height:100%;overflow:visible;transition:filter .25s,transform .35s}.contour{stroke-width:1.25}.detail{stroke-width:.78;opacity:.83}.construction{stroke-width:.55;opacity:.36}.setting{stroke-width:.62;opacity:.42}.setting-soft{stroke-width:.46;opacity:.25}.hatching{stroke-width:.48;opacity:.55}.shade{fill:currentColor;fill-opacity:.045;stroke:none}
</style>


<style scoped>
@media(max-width:700px){.contour{stroke-width:1.6}.detail{stroke-width:.88}}
</style>
