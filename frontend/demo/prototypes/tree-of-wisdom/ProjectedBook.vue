<script setup lang="ts">
import type { SampleBook } from './books';
defineProps<{book:SampleBook;large?:boolean}>();
</script>
<template>
  <div class="projected-book" :class="{large}" :style="{'--book-tint':book.color}" aria-hidden="true">
    <div class="projection-light"></div>
    <div class="projected-volume">
      <div class="volume-back"></div><div class="volume-spine"><i></i><i></i><i></i></div><div class="volume-pages"></div><div class="volume-top"></div><div class="volume-bottom"></div>
      <div class="volume-front"><span class="volume-subject">{{book.subject}}</span><span class="volume-symbol">{{book.symbol}}</span><span class="volume-title">{{book.short}}</span><span class="volume-lines"><i></i><i></i><i></i></span></div>
    </div>
    <div class="projection-base"></div>
  </div>
</template>
<style scoped>
.projected-book{--book-width:95px;--book-thickness:12px;position:relative;width:var(--book-width);height:calc(var(--book-width)*1.4);flex-shrink:0;perspective:1000px;transform-style:preserve-3d}.projected-book.large{--book-width:155px;--book-thickness:18px}
.projected-volume{position:absolute;inset:0 5px 10px 3px;transform-style:preserve-3d;transform:rotateX(6deg) rotateY(var(--cover-y,-18deg)) rotateZ(var(--cover-z,-3deg))}
.volume-front,.volume-back{position:absolute;inset:0;border:1px solid #d4efffad;border-radius:2px 4px 4px 2px;background:linear-gradient(125deg,#c1f5ff29,transparent 48%),linear-gradient(90deg,#1023359c,transparent 13%),var(--book-tint);backface-visibility:hidden}
.volume-front{transform:translateZ(calc(var(--book-thickness)/2));display:grid;grid-template-rows:auto minmax(0,1fr) auto auto;align-items:center;justify-items:center;gap:8px;padding:13% 11% 10%;color:#e8f5f5;overflow:hidden;box-shadow:inset 0 0 16px #0c203c26}
.volume-front::before{content:'';position:absolute;inset:6px;border:1px solid #d0f0ff38;border-left-color:#e0ecf555;pointer-events:none}.volume-back{transform:rotateY(180deg) translateZ(calc(var(--book-thickness)/2));background:var(--book-tint)}
.volume-spine,.volume-pages{position:absolute;top:1px;bottom:1px;width:var(--book-thickness);backface-visibility:hidden}.volume-spine{left:calc(var(--book-thickness)/-2);transform:rotateY(-90deg);background:linear-gradient(90deg,#10273fd9,#364e62),var(--book-tint);border:1px solid #b4ced58a;display:flex;flex-direction:column;justify-content:space-around;padding:10px 0}.volume-spine i{border-block:1px solid #cbb5d374;height:6px}
.volume-pages{right:calc(var(--book-thickness)/-2);transform:rotateY(90deg);background:repeating-linear-gradient(90deg,#b5c5ca 0 1px,#506574 1px 2px);border:1px solid #cfdfdd9c}.volume-top,.volume-bottom{position:absolute;left:0;right:0;height:var(--book-thickness);background:repeating-linear-gradient(#b7c9ce 0 1px,#6e828c 1px 2px);backface-visibility:hidden;border-inline:1px solid #a5c0c5}.volume-top{top:calc(var(--book-thickness)/-2);transform:rotateX(90deg)}.volume-bottom{bottom:calc(var(--book-thickness)/-2);transform:rotateX(-90deg)}
.volume-subject{font:6px/1.2 'Courier New',monospace;letter-spacing:.07em;text-transform:uppercase;max-width:100%;white-space:nowrap}.volume-symbol{font:34px/1 Georgia,serif;text-shadow:0 0 16px #b6dbe550;align-self:center;min-height:0}.volume-title{font:11px/1.15 Georgia,serif;text-align:center;text-wrap:balance;overflow-wrap:normal;word-break:normal;width:100%;max-height:2.3em;overflow:hidden}.volume-lines{display:flex;gap:4px}.volume-lines i{width:7px;border-top:1px solid #baf6ff8c}.large .volume-subject{font-size:8px}.large .volume-symbol{font-size:52px}.large .volume-title{font-size:17px}
.projection-base{position:absolute;bottom:-8px;left:-10%;right:-10%;height:19px;border:1px solid #9fdbed48;border-radius:50%;box-shadow:0 0 19px #8ae8f016,inset 0 0 15px #8ad8f011;transform:rotateX(47deg)}.projection-light{position:absolute;inset:22% -8% -6px;background:linear-gradient(0deg,#95d9f617,transparent);clip-path:polygon(28% 0,72% 0,100% 100%,0 100%)}
</style>
