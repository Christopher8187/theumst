<script setup>
defineProps({
  t: { type: Object, required: true },
  posts: { type: Array, required: true },
  editingPostId: Number,
  message: String,
  error: Boolean
});
const postDraft = defineModel("postDraft", { required: true });
defineEmits(["save", "edit", "reset", "delete", "refresh"]);

function niceDate(value, locale) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value));
}
</script>

<template>
  <section class="dashboard-card wide-card content-workspace">
    <header class="workspace-head">
      <div>
        <p class="eyebrow">{{ t.editorialDesk }}</p>
        <h1>{{ t.mediaTitle }}</h1>
        <p class="muted">{{ t.mediaText }}</p>
      </div>
      <button class="quiet-button" type="button" @click="$emit('refresh')">{{ t.refresh }}</button>
    </header>

    <div class="content-grid">
      <form class="editor-panel dashboard-form" @submit.prevent="$emit('save')">
        <div class="editor-title">
          <div><p class="eyebrow">{{ editingPostId ? t.editing : t.newStory }}</p><h2>{{ editingPostId ? t.editPost : t.publishUpdate }}</h2></div>
          <button v-if="editingPostId" class="text-button" type="button" @click="$emit('reset')">{{ t.cancel }}</button>
        </div>
        <label>{{ t.headline }}<input v-model="postDraft.title" required :placeholder="t.headlinePlaceholder"></label>
        <label>{{ t.excerpt }}<textarea v-model="postDraft.excerpt" rows="3" :placeholder="t.excerptPlaceholder"></textarea></label>
        <label>{{ t.story }}<textarea v-model="postDraft.body" rows="8" required :placeholder="t.storyPlaceholder"></textarea></label>
        <label>{{ t.imageUrl }}<input v-model="postDraft.image_url" placeholder="/images/graph.jpg"></label>
        <label>{{ t.status }}
          <select v-model="postDraft.status"><option value="published">{{ t.published }}</option><option value="draft">{{ t.draft }}</option></select>
        </label>
        <button type="submit">{{ editingPostId ? t.saveChanges : (postDraft.status === 'published' ? t.publishNow : t.saveDraft) }}</button>
        <p v-if="message" class="message key-output" :class="{ error }">{{ message }}</p>
      </form>

      <section class="catalog-panel">
        <div class="section-heading"><div><p class="eyebrow">{{ t.newsroom }}</p><h2>{{ t.allPosts }}</h2></div></div>
        <article v-for="post in posts" :key="post.media_post_id" class="content-row media-row">
          <div class="status-dot" :class="post.status"></div>
          <div class="row-copy">
            <div class="post-meta"><span :class="['status-chip', post.status]">{{ post.status === 'published' ? t.published : t.draft }}</span><span>{{ niceDate(post.published_at || post.created_at, t.dateLocale) }}</span></div>
            <h3>{{ post.title }}</h3>
            <p>{{ post.excerpt || post.body }}</p>
          </div>
          <div class="row-actions">
            <button type="button" @click="$emit('edit', post)">{{ t.edit }}</button>
            <button class="danger-button" type="button" @click="$emit('delete', post)">{{ t.delete }}</button>
          </div>
        </article>
        <div v-if="!posts.length" class="content-empty"><strong>{{ t.noPosts }}</strong><p>{{ t.noPostsText }}</p></div>
      </section>
    </div>
  </section>
</template>
