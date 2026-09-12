<script setup lang="ts">
import type { SampleBook } from './books';
defineProps<{books:SampleBook[];selected:string|null}>();
defineEmits<{select:[id:string]}>();
const places:Record<string,{left:string;top:string}>={analysis:{left:'37%',top:'49%'},symmetry:{left:'68%',top:'30%'},light:{left:'78%',top:'61%'}};
</script>
<template>
  <section class="grove" aria-label="The sacred grove">
    <div class="grove-heading"><span class="small-star">✧</span><h1>Tree of<br><em>Wisdom</em></h1><p>Where every path begins.</p></div>
    <div class="grove-paths">
      <button v-for="book in books" :key="book.id" class="branch-book" :class="{chosen:selected===book.id}" :style="places[book.id]" @click="$emit('select',book.id)">
        <span class="branch-halo"><span>{{book.symbol}}</span></span><span class="branch-caption"><small>{{book.subject}}</small><strong>{{book.title}}</strong></span>
      </button>
    </div>
    <div class="grove-root"><span></span><p>Take a little wonder with you.</p><span></span></div>
  </section>
</template>
<style scoped>
.grove{position:absolute;inset:0;color:#f1ecda}.grove-heading{position:absolute;left:6.4%;top:18%;text-shadow:0 3px 30px #0c1529}.small-star{color:#e4cd9e;font-size:28px;display:block;margin-bottom:20px}.grove-heading h1{font:400 clamp(42px,5.5vw,83px)/.96 Georgia,serif;letter-spacing:-.055em;margin:0}.grove-heading em{font-weight:400;color:#e8dcc9}.grove-heading p{font:13px/1.5 Georgia,serif;color:#d2cfcd;letter-spacing:.015em;margin-top:23px}.grove-paths{position:absolute;inset:0}.branch-book{position:absolute;transform:translate(-50%,-50%);color:#f9edd7;background:transparent;border:0;padding:16px;cursor:pointer;text-align:center;max-width:220px}.branch-halo{display:grid;place-items:center;width:53px;height:53px;margin:0 auto 13px;position:relative;border:1px solid #dfd7c363;border-radius:50%;background:#16283988;box-shadow:0 0 28px #e4dcc519,0 0 0 8px #e4dcc50b;transition:transform .35s,box-shadow .35s,background .35s}.branch-halo:before,.branch-halo:after{content:'';position:absolute;width:6px;height:6px;transform:rotate(45deg);background:#ebdab4;box-shadow:0 0 12px #eddc9b;top:-4px}.branch-halo:after{top:auto;bottom:-4px;width:3px;height:3px}.branch-halo>span{font:27px Georgia,serif}.branch-caption{display:block;padding:9px 13px 11px;background:linear-gradient(90deg,#12233800,#122338cb 20%,#122338cb 80%,#12233800);text-shadow:0 1px 9px #03101d}.branch-caption small{font:9px 'Courier New',monospace;letter-spacing:.12em;text-transform:uppercase;color:#cfbcb6;display:block;margin-bottom:5px}.branch-caption strong{font:17px/1.25 Georgia,serif;font-weight:400;display:block}.branch-book:hover .branch-halo,.branch-book:focus-visible .branch-halo,.chosen .branch-halo{transform:scale(1.15);box-shadow:0 0 44px #d7d2bb55,0 0 0 10px #e4dcc512;background:#53707bd0}.chosen .branch-caption{color:#ffedba}.grove-root{position:absolute;bottom:15%;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:17px;opacity:.7;white-space:nowrap}.grove-root p{font:italic 12px Georgia,serif;letter-spacing:.05em}.grove-root span{width:43px;height:1px;background:#e4dcc566}@media(max-width:700px){.grove-heading{top:13%;left:7%}.grove-heading h1{font-size:44px}.small-star{font-size:20px;margin-bottom:12px}.grove-heading p{font-size:11px;margin-top:15px}.branch-book{max-width:155px;padding:7px}.branch-halo{width:43px;height:43px;margin-bottom:8px}.branch-caption{padding:7px}.branch-caption strong{font-size:13px}.branch-caption small{font-size:8px}.grove-paths{top:12%;bottom:9%;}.branch-book:nth-child(1){left:25%!important;top:46%!important}.branch-book:nth-child(2){left:72%!important;top:30%!important}.branch-book:nth-child(3){left:68%!important;top:66%!important}.grove-root{bottom:14%;font-size:10px}.grove-root span{width:17px}}
</style>
