<script setup>
import BookObject from "./BookObject.vue";

defineProps({ t: Object, grimoires: Array, query: String });
defineEmits(["update:query", "open"]);
</script>

<template>
  <section class="view-pad grimoire-library">
    <header class="view-heading">
      <div><p class="demo-kicker">SUMMONED ARCHIVE</p><h1>{{ t.grimoires }}</h1></div>
      <span class="archive-count">{{ grimoires.length }}</span>
    </header>
    <label class="search-orb compact-search"><span>⌕</span><input :value="query" :placeholder="t.searchGrimoires" @input="$emit('update:query', $event.target.value)"></label>
    <p class="section-label">{{ t.recent }}</p>
    <div v-if="grimoires.length" class="grimoire-list">
      <button v-for="book in grimoires" :key="book.grimoire_id" type="button" @click="$emit('open', book)">
        <BookObject :title="book.title" />
        <div><h2>{{ book.title }}</h2><p>{{ book.summary }}</p><span>{{ book.completed_count }} / {{ book.knowledge_count }} · {{ t.completed }}</span></div>
        <strong>{{ t.open }} →</strong>
      </button>
    </div>
    <p v-else class="empty-state">{{ t.noGrimoires }}</p>
  </section>
</template>
