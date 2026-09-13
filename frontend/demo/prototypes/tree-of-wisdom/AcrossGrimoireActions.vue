<script setup lang="ts">
import { acrossActions } from './designOptions';
import { useWisdomI18n } from './i18n';
defineProps<{count:number;collectionActive:boolean}>();
defineEmits<{collection:[];action:[id:string]}>();
const {t}=useWisdomI18n();
</script>

<template>
  <nav class="across-group" :aria-label="t.acrossGrimoires">
    <span class="scope-label">{{t.acrossGrimoires}}</span>
    <div class="across-options">
      <button class="collection-action" :aria-pressed="collectionActive" @click="$emit('collection')">
        <span class="action-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4"/></svg></span>
        <strong>{{t.collection}}</strong><small class="collection-count">{{String(count).padStart(2,'0')}}</small>
      </button>
      <button v-for="action in acrossActions" :key="action.id" :aria-label="t[action.id]+' · '+t.acrossGrimoires" :title="t[action.description]" @click="$emit('action',action.id)">
        <span class="action-mark" aria-hidden="true"><i>{{action.symbol}}</i></span><strong>{{t[action.id]}}</strong>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.across-group{position:fixed;z-index:12;top:50%;left:4.5%;transform:translateY(-50%);width:180px;color:#d8e6ed;font-family:'Bahnschrift','Segoe UI',sans-serif;transition:opacity .2s}
.scope-label{display:block;margin:0 0 12px 13px;font:10px/1.4 'Courier New',monospace;color:#e1e9ee;text-shadow:0 1px 7px #10273b}
.across-options{position:relative;padding:7px;background:linear-gradient(140deg,#18384adf,#242e43e8);border:1px solid #b6d7e466;border-radius:4px 20px 4px 4px;backdrop-filter:blur(18px);box-shadow:0 16px 38px #10263a26,inset 0 1px #dfedf411}
.across-options:before{content:'';position:absolute;left:-1px;top:24px;bottom:24px;width:1px;background:linear-gradient(transparent,#b9dde7aa,transparent);pointer-events:none}
.across-options>button{position:relative;display:grid;grid-template-columns:32px minmax(0,1fr) auto;gap:10px;align-items:center;width:100%;min-height:61px;padding:9px 7px;text-align:left;background:none;border:1px solid transparent;border-radius:3px;color:inherit;transition:background .18s,border-color .18s}
.across-options strong{font-size:12px;font-weight:400;line-height:1.3}
.action-mark{box-sizing:border-box;display:grid;place-items:center;width:32px;height:32px;min-width:32px;border:1px solid #aac7dc28;border-radius:3px;color:#c8b9de;background:#b5cde504}
.action-mark i{display:block;font:normal 25px/1 'Yu Mincho','SimSun',serif;transform:translateY(-.025em)}
.action-mark svg{display:block;width:23px;height:23px;fill:none;stroke:#bfdce4;stroke-width:1.15;stroke-linecap:round;stroke-linejoin:round}
.collection-count{font:10px/1 'Courier New',monospace;color:#94b8c8}
.collection-action{margin-bottom:8px}
.collection-action:after{content:'';position:absolute;left:7px;right:7px;bottom:-5px;height:1px;background:#b8cfe72b}
.across-options>button:hover{background:#c8b2df10;border-color:#d2c2e634}
.across-options>button[aria-pressed=true]{background:#a4dce715;box-shadow:inset 2px 0 #b1dee4;border-color:#b1dce33d}
.across-options>button[aria-pressed=true] .action-mark{color:#dcf4f5;border-color:#b5dce569}
.across-options>button:focus-visible{outline:1px solid #d5bce6;outline-offset:2px;background:#c8b2df14}
@media(max-width:1000px) and (min-width:701px){.across-group{left:3%;width:170px}.across-options>button{gap:8px;padding-inline:5px}}
@media(max-width:700px){
  .across-group{left:13px;right:13px;top:calc(145px + env(safe-area-inset-top));width:auto;transform:none}
  .scope-label{display:none}.across-options{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));padding:5px;gap:3px;border-radius:4px 17px 4px 4px}
  .across-options:before{display:none}.across-options>button{display:flex;flex-direction:column;justify-content:flex-start;gap:7px;min-height:70px;padding:8px 1px 5px;text-align:center}
  .action-mark{width:28px;height:28px;min-width:28px;flex:0 0 28px}.action-mark i{font-size:22px}.action-mark svg{width:21px;height:21px}
  .across-options strong{font-size:10px;line-height:1.25}.collection-count{display:none}.collection-action{margin:0}.collection-action:after{left:auto;right:-3px;top:9px;bottom:9px;width:1px;height:auto}
}
</style>
