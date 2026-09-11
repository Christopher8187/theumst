<script setup>
defineProps({
  t: { type: Object, required: true },
  posts: { type: Array, required: true },
  editingPostId: Number,
  message: String,
  error: Boolean,
  saving: Boolean,
  createRetryPending: Boolean,
  announcementQueued: Boolean,
  emailPreview: Object,
  previewLoading: Boolean,
  previewError: String
});
const postDraft = defineModel("postDraft", { required: true });
defineEmits(["save", "edit", "reset", "delete", "refresh", "preview", "retry-create"]);

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
          <button v-if="editingPostId" class="text-button" type="button" :disabled="saving" @click="$emit('reset')">{{ t.cancel }}</button>
        </div>
        <fieldset class="media-fields" :disabled="saving || createRetryPending">
        <label>{{ t.headline }}<input v-model="postDraft.title" required :placeholder="t.headlinePlaceholder"></label>
        <label>{{ t.excerpt }}<textarea v-model="postDraft.excerpt" rows="3" :placeholder="t.excerptPlaceholder"></textarea></label>
        <label>{{ t.story }}<textarea v-model="postDraft.body" rows="8" required :placeholder="t.storyPlaceholder"></textarea></label>
        <label>{{ t.imageUrl }}<input v-model="postDraft.image_url" placeholder="/images/graph.jpg"></label>
        <label>{{ t.status }}
          <select v-model="postDraft.status"><option value="published">{{ t.published }}</option><option value="draft">{{ t.draft }}</option></select>
        </label>
        <section class="announcement-options" :aria-label="t.newsAnnouncement">
          <h3>{{ t.newsAnnouncement }}</h3>
          <label>{{ t.emailIntroduction }}<textarea v-model="postDraft.email_introduction" rows="4" maxlength="5000" :required="postDraft.announce" :placeholder="t.emailIntroductionPlaceholder"></textarea></label>
          <p class="muted">{{ t.emailIntroductionHelp }}</p>
          <label class="announcement-choice">
            <input v-model="postDraft.announce" type="checkbox" :disabled="postDraft.status !== 'published' || announcementQueued">
            <span>{{ t.announceSubscribers }}</span>
          </label>
          <p class="muted">{{ announcementQueued ? t.announcementAlreadyQueued : (postDraft.status !== 'published' ? t.announcementPublishFirst : t.announcementConsent) }}</p>
          <button class="quiet-button" type="button" :disabled="previewLoading || !postDraft.title.trim() || !postDraft.email_introduction.trim()" @click="$emit('preview')">{{ previewLoading ? t.emailPreviewLoading : t.previewEmail }}</button>
          <p v-if="previewError" role="alert" class="message error">{{ previewError }}</p>
        </section>
        <button type="submit">{{ saving ? t.saving : (editingPostId ? t.saveChanges : (postDraft.status === 'published' ? t.publishNow : t.saveDraft)) }}</button>
        </fieldset>
        <p v-if="message" role="status" class="message key-output" :class="{ error }">{{ message }}</p>
        <button v-if="createRetryPending" type="button" :disabled="saving" @click="$emit('retry-create')">{{ saving ? t.saving : t.retrySavedSubmission }}</button>
        <section v-if="emailPreview" class="email-preview" :aria-label="t.emailPreviewTitle">
          <h3>{{ t.emailPreviewTitle }}</h3>
          <p><strong>{{ t.emailSubject }}</strong> {{ emailPreview.subject }}</p>
          <p class="muted">{{ t.emailPreviewNotice }}</p>
          <iframe :srcdoc="emailPreview.html" sandbox="" referrerpolicy="no-referrer" :title="t.emailPreviewTitle"></iframe>
          <details><summary>{{ t.plainTextVersion }}</summary><pre>{{ emailPreview.text }}</pre></details>
        </section>
      </form>

      <section class="catalog-panel">
        <div class="section-heading"><div><p class="eyebrow">{{ t.newsroom }}</p><h2>{{ t.allPosts }}</h2></div></div>
        <article v-for="post in posts" :key="post.media_post_id" class="content-row media-row">
          <div class="status-dot" :class="post.status"></div>
          <div class="row-copy">
            <div class="post-meta"><span :class="['status-chip', post.status]">{{ post.status === 'published' ? t.published : t.draft }}</span><span>{{ niceDate(post.published_at || post.created_at, t.dateLocale) }}</span><span v-if="post.announcement_queued_at" class="status-chip">{{ t.announcementQueued }}</span></div>
            <h3>{{ post.title }}</h3>
            <p>{{ post.excerpt || post.body }}</p>
          </div>
          <div class="row-actions">
            <button type="button" :disabled="saving" @click="$emit('edit', post)">{{ t.edit }}</button>
            <button class="danger-button" type="button" :disabled="saving || createRetryPending" @click="$emit('delete', post)">{{ t.delete }}</button>
          </div>
        </article>
        <div v-if="!posts.length" class="content-empty"><strong>{{ t.noPosts }}</strong><p>{{ t.noPostsText }}</p></div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.media-fields { display: grid; gap: 16px; min-width: 0; margin: 0; padding: 0; border: 0; }
.announcement-options { display: grid; gap: 12px; padding-top: 12px; border-top: 1px solid var(--line); }
.announcement-options h3, .announcement-options p { margin: 0; }
.announcement-choice { display: flex; align-items: flex-start; gap: 10px; }
.announcement-choice input { flex: 0 0 auto; width: 18px; min-height: 18px; margin: 3px 0 0; }
.email-preview { min-width: 0; }
.email-preview iframe { display: block; width: 100%; height: 670px; margin: 12px 0; border: 1px solid var(--line); background: #f8f2e5; }
.email-preview pre { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
