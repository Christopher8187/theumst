<script setup>
import { onMounted, ref } from "vue";
import { renderMath } from "../math";
defineProps({ t: Object, results: Array, status: String, error: String });
defineEmits(["close", "open"]);

const closeButton = ref(null);
onMounted(() => closeButton.value?.focus());
</script>

<template>
  <section class="search-panel" role="region" aria-labelledby="similar-panel-title" tabindex="-1" @keydown.esc.stop="$emit('close')">
    <header><div><p class="demo-kicker">{{ t.embeddingSearch }}</p><h2 id="similar-panel-title">{{ t.cluster }}</h2></div><button ref="closeButton" type="button" :aria-label="t.closeSimilar" @click="$emit('close')">×</button></header>
    <p class="search-method">{{ t.similarityMethod }}</p>
    <p v-if="status === 'idle'" class="empty-state">{{ t.similarPrompt }}</p>
    <div v-else-if="status === 'loading'" class="search-loader" role="status"><span></span><span></span><span></span><p>{{ t.loadingSimilar }}</p></div>
    <div v-else-if="status === 'results'" class="resonance-list" :aria-label="t.similarResults">
      <button v-for="result in results" :key="`${result.grimoire_id}:${result.knowledge_id}`" type="button" @click="$emit('open', result)">
        <div><span>{{ result.book_title }}</span><strong>{{ result.label }}</strong></div>
        <p v-html="renderMath(result.statement || '')"></p>
        <i>{{ t.similarityStrength }} {{ Number.isFinite(result.similarity_score) ? result.similarity_score.toFixed(3) : '—' }}</i>
      </button>
    </div>
    <p v-else-if="status === 'empty'" class="empty-state" role="status">{{ t.noResults }}</p>
    <p v-else-if="status === 'unavailable'" class="empty-state" role="status">{{ t.similarUnavailable }}</p>
    <p v-else-if="status === 'error'" class="empty-state" role="alert">{{ error || t.similarError }}</p>
  </section>
</template>
