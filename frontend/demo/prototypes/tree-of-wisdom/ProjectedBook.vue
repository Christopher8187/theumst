<script setup lang="ts">
import type { SampleBook } from './books';
defineProps<{ book: SampleBook; large?: boolean }>();
</script>

<template>
  <div class="projected-book" :class="{ large }" :style="{'--book-tint':book.color}" aria-hidden="true">
    <div class="projection-light"></div>
    <div class="projected-volume">
      <span class="volume-subject">{{book.subject}}</span>
      <span class="volume-symbol">{{book.symbol}}</span>
      <span class="volume-title">{{book.title}}</span>
      <span class="volume-lines"><i></i><i></i><i></i></span>
    </div>
    <div class="projection-base"></div>
  </div>
</template>

<style scoped>
.projected-book{position:relative;width:95px;height:132px;perspective:700px;flex-shrink:0;--book-tint:#526c89}.projected-volume{position:absolute;inset:6px 13px 13px 8px;display:flex;align-items:center;flex-direction:column;padding:12px 6px 8px;color:#ebfbff;background:linear-gradient(125deg,#c1f5ff23,transparent 45%),linear-gradient(90deg,#060e1e88,transparent 15%),var(--book-tint);border:1px solid #d4f6ff8c;box-shadow:3px 2px 0 #a2d4e2,5px 3px 0 #1e4054,0 0 20px #a3a5ef26;transform:rotateY(-22deg) rotateZ(-5deg);transition:transform .5s,box-shadow .5s;border-radius:2px 4px 4px 2px}.projected-volume:before{content:'';position:absolute;inset:5px;border:1px solid #d0f0ff2f}.volume-subject{font:5px/1.5 'Courier New',monospace;letter-spacing:.1em;text-transform:uppercase}.volume-symbol{font:32px/1 Georgia,serif;margin:10px 0 6px;text-shadow:0 0 14px #c5f6fa}.volume-title{font:9px/1.2 Georgia,serif;text-align:center}.volume-lines{display:flex;gap:3px;margin-top:auto}.volume-lines i{width:7px;border-top:1px solid #baf6ff99}.projection-base{position:absolute;bottom:0;left:2%;right:2%;height:15px;border:1px solid #85e4f563;border-radius:50%;box-shadow:0 0 20px #8ae8f026,inset 0 0 15px #8ad8f019}.projection-light{position:absolute;inset:35% -8% 0;background:linear-gradient(0deg,#95d9f620,transparent);clip-path:polygon(28% 0,72% 0,100% 100%,0 100%)}.large{width:151px;height:211px}.large .projected-volume{padding:22px 10px 15px;inset:8px 19px 18px 13px}.large .volume-subject{font-size:7px}.large .volume-symbol{font-size:51px;margin:22px 0 12px}.large .volume-title{font-size:14px}.large .projection-base{height:20px}button:hover .projected-volume,button:focus-visible .projected-volume{transform:rotateY(-9deg) rotateZ(-2deg) translateY(-4px);box-shadow:3px 2px 0 #b9eaff,5px 3px 0 #1e4054,0 0 28px #b1cdf84d}
</style>
