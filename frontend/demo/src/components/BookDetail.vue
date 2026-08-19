<script setup>
import BookObject from "./BookObject.vue";

defineProps({ t: Object, book: Object, contents: Array, summoning: Boolean });
defineEmits(["summon"]);
</script>

<template>
  <section v-if="book" class="book-detail view-pad">
    <header class="view-heading">
      <div>
        <p class="demo-kicker">{{ t.title }}</p>
        <h1>{{ book.title }}</h1>
      </div>
      <span class="edition-chip">{{ book.version }}</span>
    </header>

    <div class="book-detail-grid">
      <div class="book-pedestal">
        <BookObject :title="book.title" large />
        <p><span>{{ t.isbn }}:</span> {{ book.isbn || '—' }}</p>
      </div>
      <div class="summary-oracle">
        <div class="oracle-head">
          <span class="oracle-sigil">✦</span>
          <div><p class="demo-kicker">UMST SYNTHESIS</p><h2>{{ t.aiSummary }}</h2></div>
        </div>
        <p class="summary-copy">{{ book.summary || book.title }}</p>
        <h3>{{ t.contents }}</h3>
        <ol class="contents-list">
          <li v-for="section in contents" :key="section.section_id">
            <span>{{ section.section_number }}</span>{{ section.section_name }}
          </li>
        </ol>
        <button class="primary-button summon-button" :class="{ summoning }" type="button" @click="$emit('summon')">
          <span>✧</span>{{ book.summoned ? t.summoned : t.summon }}
        </button>
      </div>
    </div>
  </section>
</template>
