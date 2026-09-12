<script setup lang="ts">
import { variants, designNames, type Variant, type BriefDesign, type ActionPlacement } from './designOptions';
import { useWisdomI18n } from './i18n';
const props=defineProps<{value:Variant;brief:BriefDesign;actions:ActionPlacement}>();
const emit=defineEmits<{change:[value:Variant]}>();
const {t}=useWisdomI18n();
function cycle(step:number){emit('change',variants[(variants.indexOf(props.value)+step+variants.length)%variants.length])}
function keydown(event:KeyboardEvent){
  if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();event.stopPropagation();cycle(event.key==='ArrowLeft'?-1:1)}
}
</script>
<template>
  <aside class="round-switcher" :aria-label="t.prototype" @keydown="keydown">
    <div class="round-options"><button :aria-label="t.previousVariant" @click="cycle(-1)">‹</button><button v-for="value in variants" :key="value" :class="{'group-start':value==='D'}" :aria-label="t.variant+' '+value+': '+t[designNames[value]]" :aria-pressed="value===props.value" @click="emit('change',value)">{{value}}</button><button :aria-label="t.nextVariant" @click="cycle(1)">›</button></div>
    <p><span>{{t.brief}} {{brief}} · {{t[designNames[brief]]}}</span><i>/</i><span>{{t.actions}} {{actions}} · {{t[designNames[actions]]}}</span></p>
  </aside>
</template>
<style scoped>
.round-switcher{position:fixed;z-index:30;bottom:16px;left:50%;transform:translateX(-50%);width:max-content;max-width:calc(100vw - 28px);padding:8px 13px 9px;background:#0d2135f5;border:1px solid #91a8bc88;color:#bdd0df;box-shadow:0 8px 25px #10203030;font-family:'Bahnschrift','Segoe UI',sans-serif;pointer-events:auto}.round-options{display:flex;justify-content:center;gap:5px}.round-options button{background:none;border:1px solid transparent;color:#bed2e0;width:35px;height:30px;font:12px 'Courier New',monospace;cursor:pointer}.round-options button[aria-pressed=true]{background:#cedce6;color:#142c42;border-color:#f2f4f8}.round-options button:first-child,.round-options button:last-child{font-size:22px;width:25px}.round-options .group-start{margin-left:12px}.round-switcher p{display:flex;align-items:center;justify-content:center;gap:10px;font:9px/1.5 'Courier New',monospace;margin:6px 0 0}.round-switcher i{color:#687e92;font-style:normal}@media(max-width:700px){.round-switcher{bottom:10px;padding:6px 8px 7px;width:calc(100vw - 28px)}.round-options{gap:2px}.round-options button{height:27px;width:30px}.round-options .group-start{margin-left:8px}.round-switcher p{font-size:7px;gap:7px}.round-switcher p span{white-space:nowrap}}
</style>

<style scoped>
.round-options button{min-height:38px}.round-switcher{bottom:max(15px,env(safe-area-inset-bottom))}@media(max-width:700px){.round-switcher{bottom:max(9px,env(safe-area-inset-bottom))}.round-options button{min-height:40px}.round-switcher p{font-size:8px;flex-wrap:wrap;gap:3px 7px;margin-top:3px}}
</style>
