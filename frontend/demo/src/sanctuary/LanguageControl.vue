<script setup lang="ts">
import { useWisdomI18n, languageOptions } from './i18n';
const {t,lang,setLang}=useWisdomI18n();
</script>

<template>
  <label class="language-control" :title="t.language">
    <svg class="language-mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h12M9 3v2M5 5c.8 5 4.2 8 8 10M13 5c-.8 5-4.2 8-8 10M13 21l4-10 4 10M14.3 18h5.4"/></svg>
    <select :aria-label="t.language" :value="lang" @change="setLang(($event.target as HTMLSelectElement).value)">
      <option v-for="option in languageOptions" :key="option[0]" :value="option[0]">{{option[1]}}</option>
    </select>
    <svg class="language-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>
  </label>
</template>

<style scoped>
.language-control{position:relative;display:flex;align-items:center;gap:8px;flex-shrink:0;height:44px;padding:0 11px;color:#d6d9e9;border:1px solid #bfd2e25c;border-radius:4px 13px 4px 4px;background:#203549df;backdrop-filter:blur(16px)}
.language-control svg{display:block;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;pointer-events:none;flex-shrink:0}
.language-mark{width:21px;height:21px;stroke-width:1.4}
.language-control select{appearance:none;min-width:68px;height:100%;padding:0 17px 0 0;border:0;border-radius:0;background:transparent;color:#e1e9f1;font:12px/1 'Bahnschrift','Segoe UI',sans-serif;cursor:pointer}
.language-control option{background:#203549;color:#e7edf4}
.language-chevron{position:absolute;right:10px;top:50%;transform:translateY(-50%);width:12px;height:12px;stroke-width:1.4}
.language-control:focus-within{outline:1px solid #c5b9df;outline-offset:3px}.language-control select:focus-visible{outline:none}
@media(max-width:700px){.language-control{gap:6px;padding-inline:8px}.language-mark{width:20px;height:20px}.language-control select{min-width:59px;font-size:11px}.language-chevron{right:8px}}
</style>
