<script setup>
import { onMounted, ref } from "vue";
import { renderMath } from "../math";
defineProps({ t: Object, results: Array, status: String, error: String, kind: String });
defineEmits(["close", "open"]);

const closeButton = ref(null);
onMounted(() => closeButton.value?.focus());
</script>

<template>
  <section class="search-panel" role="region" aria-labelledby="similar-panel-title" tabindex="-1" @keydown.esc.stop="$emit('close')">
    <header><div><p class="demo-kicker">{{ t.embeddingSearch }}</p><h2 id="similar-panel-title">{{ kind==='crystallize'?t.crystallization:t.cluster }}</h2></div><button ref="closeButton" type="button" :aria-label="t.close" @click="$emit('close')">×</button></header>
    <p class="search-method">{{ kind==='crystallize'?t.crystalMethod:t.similarityMethod }}</p>
    <p v-if="status === 'idle'" class="empty-state">{{ t.similarPrompt }}</p>
    <div v-else-if="status === 'loading'" class="search-loader" role="status"><span></span><span></span><span></span><p>{{ t.loadingSimilar }}</p></div>
    <div v-else-if="status === 'results'" class="resonance-list" :aria-label="t.similarResults">
      <button v-for="result in results" :key="`${result.grimoire_id}:${result.knowledge_id}`" type="button" @click="$emit('open', result)">
        <div><span>{{ result.book_title }}</span><strong v-html="renderMath(result.label || '')"></strong></div>
        <p v-html="renderMath(result.statement || '')"></p>
        <i v-if="kind!=='crystallize'">{{ t.similarityStrength }} {{ Number.isFinite(result.similarity_score) ? result.similarity_score.toFixed(3) : '—' }}</i>
        <i v-else-if="result.is_default_in_crystal">{{ t.preferredInstance }}</i>
      </button>
    </div>
    <p v-else-if="status === 'empty'" class="empty-state" role="status">{{ t.noResults }}</p>
    <p v-else-if="status === 'unavailable'" class="empty-state" role="status">{{ t.similarUnavailable }}</p>
    <p v-else-if="status === 'error'" class="empty-state" role="alert">{{ t.similarError }}</p>
  </section>
</template>
