<script setup>
import BookObject from "./BookObject.vue";

defineProps({ t: Object, books: Array, query: String });
defineEmits(["update:query", "open", "grimoires", "soon"]);
</script>

<template>
  <section class="library-view view-pad">
    <header class="view-heading library-heading">
      <div>
        <p class="demo-kicker">UMST · 書庫</p>
        <h1>{{ t.library }}</h1>
      </div>
      <button class="ghost-button" type="button" @click="$emit('grimoires')">✦ {{ t.grimoires }}</button>
    </header>

    <label class="search-orb">
      <span>⌕</span>
      <input :value="query" :placeholder="t.searchBooks" @input="$emit('update:query', $event.target.value)">
      <kbd>/</kbd>
    </label>

    <p class="section-label">{{ t.recommended }}</p>
    <div v-if="books.length" class="book-grid">
      <button v-for="book in books" :key="book.grimoire_id" type="button" class="book-button" @click="$emit('open', book)">
        <BookObject
          :title="book.title"
          :progress="book.knowledge_count ? Math.round(100 * book.completed_count / book.knowledge_count) : 0"
        />
        <span>{{ book.publisher }}</span>
      </button>
    </div>
    <p v-else class="empty-state">
      {{ query.trim() ? t.emptySearch : (t.libraryUnavailable || "Learning materials are not available here right now.") }}
    </p>

    <div class="library-actions">
      <button v-for="action in ['review', 'advice', 'expand', 'generate']" :key="action" type="button" @click="$emit('soon')">
        <span>{{ { review: '覺', advice: '意', expand: '道', generate: '境' }[action] }}</span>
        {{ t[action] }}
      </button>
    </div>
  </section>
</template>
