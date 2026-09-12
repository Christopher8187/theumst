<script setup lang="ts">
import type { SampleBook } from './books';
import { useWisdomI18n } from './i18n';
const {t}=useWisdomI18n();
defineProps<{book:SampleBook;added:boolean}>();
defineEmits<{add:[];enter:[];preview:[]}>();
</script>

<template>
  <section class="grimoire-detail" :key="book.id" :aria-label="t.selected">
    <div class="detail-heading"><p class="tech-label">{{book.subject}}<span>◦ {{book.count}} {{book.id==='analysis'?t.objects:t.passages}}</span></p><h2>{{book.title}}</h2></div>
    <p class="grimoire-summary">{{book.summary||book.title}}</p>
    <div class="detail-action"><button class="summon-action" @click="added?$emit('enter'):$emit('add')"><span>{{added?t.enter:t.add}}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></button><span class="added-state" :class="{added}">{{added?'✓ '+t.inCollection:t.available}}</span></div>
    <button class="preview-action" @click="$emit('preview')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v15M3 4c4-1 6 0 9 2 3-2 5-3 9-2v14c-4-1-6 0-9 2-3-2-5-3-9-2Z"/></svg>{{t.brief}} <span>↗</span></button>
  </section>
</template>

<style scoped>
.grimoire-detail{min-width:0;color:#e6f1f6;animation:detail-in .35s ease-out}.detail-heading h2{font:400 clamp(23px,2.35vw,35px)/1.08 'Bahnschrift','Segoe UI',sans-serif;letter-spacing:-.025em;margin:15px 0 18px;text-wrap:balance}.tech-label{font:9px/1.5 'Courier New',monospace;letter-spacing:.11em;text-transform:uppercase;color:#a5e0e7;margin:0;display:flex;gap:15px;flex-wrap:wrap}.tech-label span{letter-spacing:.025em;color:#b9b8d4}.grimoire-summary{font:13px/1.7 'Segoe UI',sans-serif;color:#c6d5df;margin:0 0 24px;max-width:48ch}.detail-action{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.summon-action{min-height:43px;display:flex;align-items:center;justify-content:space-between;gap:28px;border:1px solid #9beaf0a8;background:#8ce0eb16;color:#b6f7fa;box-shadow:inset 0 0 15px #9ee7ef0c;padding:11px 15px;cursor:pointer;border-radius:5px 15px 5px 5px;font:13px 'Bahnschrift','Segoe UI',sans-serif;transition:background .2s,box-shadow .2s}.summon-action:hover{background:#a5e8fa30;box-shadow:0 0 19px #9fe5ed24}.summon-action svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.6}.added-state{font:9px 'Courier New',monospace;color:#afa7c4}.added-state.added{color:#b6ddd2}@keyframes detail-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style>
<style scoped>
.preview-action{display:flex;align-items:center;gap:10px;min-height:43px;margin-top:18px;padding:11px 15px;border:1px solid #d7b6e16b;border-radius:5px 15px 5px 5px;color:#e4cfed;background:#c4a4dd0b;font-size:12px}.preview-action:hover{background:#d4b5e721}.preview-action svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.3}.preview-action>span{margin-left:8px}
</style>
