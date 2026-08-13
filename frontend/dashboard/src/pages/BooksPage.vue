<script setup>
defineProps({
  t: { type: Object, required: true },
  books: { type: Array, required: true },
  editingBookId: Number,
  message: String,
  error: Boolean
});
const bookDraft = defineModel("bookDraft", { required: true });
defineEmits(["save", "edit", "reset", "delete", "refresh"]);
</script>

<template>
  <section class="dashboard-card wide-card content-workspace">
    <header class="workspace-head">
      <div>
        <p class="eyebrow">{{ t.libraryOperations }}</p>
        <h1>{{ t.booksTitle }}</h1>
        <p class="muted">{{ t.booksText }}</p>
      </div>
      <button class="quiet-button" type="button" @click="$emit('refresh')">{{ t.refresh }}</button>
    </header>

    <div class="workspace-stats">
      <article><strong>{{ books.length }}</strong><span>{{ t.booksTracked }}</span></article>
      <article><strong>{{ books.reduce((sum, book) => sum + Number(book.section_count || 0), 0) }}</strong><span>{{ t.sectionsMapped }}</span></article>
      <article><strong>{{ books.reduce((sum, book) => sum + Number(book.knowledge_count || 0), 0) }}</strong><span>{{ t.knowledgeObjects }}</span></article>
    </div>

    <div class="content-grid">
      <form class="editor-panel dashboard-form" @submit.prevent="$emit('save')">
        <div class="editor-title">
          <div>
            <p class="eyebrow">{{ editingBookId ? t.editing : t.newEntry }}</p>
            <h2>{{ editingBookId ? t.editBook : t.addBook }}</h2>
          </div>
          <button v-if="editingBookId" class="text-button" type="button" @click="$emit('reset')">{{ t.cancel }}</button>
        </div>
        <label>{{ t.bookTitle }}<input v-model="bookDraft.title" required :placeholder="t.bookTitlePlaceholder"></label>
        <div class="form-pair">
          <label>{{ t.publisher }}<input v-model="bookDraft.publisher"></label>
          <label>{{ t.isbn }}<input v-model="bookDraft.isbn"></label>
        </div>
        <div class="form-pair">
          <label>{{ t.publishDate }}<input v-model="bookDraft.publish_date" placeholder="2026 or 2026-08-12"></label>
          <label>{{ t.version }}<input v-model="bookDraft.version" placeholder="1st edition"></label>
        </div>
        <label>{{ t.sourceKey }}<input v-model="bookDraft.source_key" placeholder="publisher/title-v1"></label>
        <button type="submit">{{ editingBookId ? t.saveChanges : t.addBook }}</button>
        <p v-if="message" class="message key-output" :class="{ error }">{{ message }}</p>
      </form>

      <section class="catalog-panel">
        <div class="section-heading">
          <div><p class="eyebrow">{{ t.catalog }}</p><h2>{{ t.currentBooks }}</h2></div>
        </div>
        <article v-for="book in books" :key="book.grimoire_id" class="content-row">
          <div class="row-mark">{{ String(book.title || '?').slice(0, 1).toUpperCase() }}</div>
          <div class="row-copy">
            <h3>{{ book.title }}</h3>
            <p>{{ book.publisher || t.unknownPublisher }} · {{ book.publish_date || t.dateNotSet }}</p>
            <div class="row-tags">
              <span>{{ book.section_count }} {{ t.sections }}</span>
              <span>{{ book.knowledge_count }} {{ t.objects }}</span>
              <span v-if="book.version">{{ book.version }}</span>
            </div>
          </div>
          <div class="row-actions">
            <button type="button" @click="$emit('edit', book)">{{ t.edit }}</button>
            <button class="danger-button" type="button" @click="$emit('delete', book)">{{ t.delete }}</button>
          </div>
        </article>
        <div v-if="!books.length" class="content-empty"><strong>{{ t.noBooks }}</strong><p>{{ t.noBooksText }}</p></div>
      </section>
    </div>
  </section>
</template>
