<script setup lang="ts">
import { computed } from 'vue';
import { useWisdomI18n } from '../i18n';

defineOptions({ inheritAttrs: false });
const model = defineModel<'A'|'B'|'C'>({ required: true });
const isPrototype = import.meta.env.DEV;
const { lang } = useWisdomI18n();
const keys = ['A', 'B', 'C'] as const;
const copy = computed(() => lang.value === 'zh'
  ? { label: '左页设计', previous: '上一个设计', next: '下一个设计', names: ['学习单', '日常笔记', '留白手记'] }
  : lang.value === 'ja'
    ? { label: '左ページの試作', previous: '前のデザイン', next: '次のデザイン', names: ['学習シート', '日々のノート', 'フレームノート'] }
    : { label: 'Left page study', previous: 'Previous design', next: 'Next design', names: ['Study sheet', 'Daily notebook', 'Open frame'] });
function cycle(direction: number) { model.value = keys[(keys.indexOf(model.value) + direction + keys.length) % keys.length]; }
</script>

<template>
  <Teleport to="body">
  <nav v-if="isPrototype" v-bind="$attrs" class="notebook-comparison" :aria-label="copy.label"
    @keydown.left.prevent="cycle(-1)" @keydown.right.prevent="cycle(1)">
    <span class="comparison-label">{{copy.label}}</span>
    <button type="button" class="comparison-arrow" :aria-label="copy.previous" @click="cycle(-1)">‹</button>
    <button v-for="(key,i) in keys" :key="key" type="button" :aria-pressed="model===key"
      :aria-label="key+' · '+copy.names[i]" @click="model=key"><b>{{key}}</b><span>{{copy.names[i]}}</span></button>
    <button type="button" class="comparison-arrow" :aria-label="copy.next" @click="cycle(1)">›</button>
  </nav>
  </Teleport>
</template>

<style scoped>
.notebook-comparison{position:fixed;z-index:90;left:50%;bottom:9px;transform:translateX(-50%);display:flex;align-items:center;gap:4px;padding:6px 8px;border:1px solid #b6c6c19c;border-radius:4px;background:#101f2df5;box-shadow:0 5px 22px #07121b66;color:#e5ebe7;font:11px 'Bahnschrift','Segoe UI',sans-serif;white-space:nowrap}
.comparison-label{color:#adbdc3;font:9px 'Courier New',monospace;letter-spacing:.04em;padding:0 8px}
.notebook-comparison button{display:flex;align-items:center;gap:7px;background:transparent;border:1px solid transparent;color:#acbdc5;padding:7px 9px;min-height:32px;cursor:pointer;border-radius:2px;font:inherit}
.notebook-comparison button b{font:11px 'Courier New',monospace;color:#dfd2e3}
.notebook-comparison button[aria-pressed=true]{background:#dce3db;color:#213943;border-color:#f0f1e7}.notebook-comparison button[aria-pressed=true] b{color:#425163}
.notebook-comparison button:hover{border-color:#b9d8d69c}.notebook-comparison button:focus-visible{outline:2px solid #d8c3e4;outline-offset:2px}
.notebook-comparison .comparison-arrow{font-size:21px;padding:0 6px;min-width:28px;justify-content:center}
@media(max-width:700px){.comparison-label{display:none}.notebook-comparison{bottom:max(8px,env(safe-area-inset-bottom));max-width:calc(100vw - 16px);gap:2px;padding:5px}.notebook-comparison button{padding:6px 8px;gap:5px;min-height:37px}.notebook-comparison button span{display:none}.notebook-comparison button[aria-pressed=true] span{display:inline;font-size:10px}.notebook-comparison .comparison-arrow{min-width:27px}}
</style>
