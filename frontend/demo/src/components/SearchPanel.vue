<script setup>
import { renderMath } from "../math";
defineProps({ t: Object, results: Array, loading: Boolean });
defineEmits(["close", "open"]);
</script>

<template>
  <section class="search-panel">
    <header><div><p class="demo-kicker">EMBEDDING SEARCH</p><h2>{{ t.similarity }}</h2></div><button type="button" @click="$emit('close')">×</button></header>
    <p class="search-method">{{ t.similarityMethod }}</p>
    <div v-if="loading" class="search-loader"><span></span><span></span><span></span></div>
    <div v-else-if="results.length" class="resonance-list">
      <button v-for="result in results" :key="result.knowledge_id" type="button" @click="$emit('open', result)">
        <div><span>{{ result.book_title }}</span><strong>{{ result.label }}</strong></div>
        <p v-html="renderMath(result.statement)"></p>
        <i>{{ Math.round(result.weighted_score * 100) }}%</i>
      </button>
    </div>
    <p v-else class="empty-state">{{ t.noResults }}</p>
  </section>
</template>
