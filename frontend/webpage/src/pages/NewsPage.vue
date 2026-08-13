<script setup>
import { onMounted, ref } from "vue";
import { apiFetch, apiUrl, assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean });
defineEmits(["navigate", "set-language", "login", "signup"]);
const posts = ref([]);
const loading = ref(true);

function postImage(value, index) {
  if (!value) return assetUrl(index % 2 ? "graph.jpg" : "cave.jpg");
  return /^https?:\/\//.test(value) ? value : apiUrl(value);
}

onMounted(async () => {
  try {
    const res = await apiFetch("/api/news");
    if (res.ok) posts.value = (await res.json()).posts;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <SiteHeader :tr="tr" title-key="news.title" :session="session" @navigate="$emit('navigate', $event)" @set-language="$emit('set-language', $event)" />
  <main class="site-container news-page">
    <div class="news-page-intro"><p>{{ tr("news.intro") }}</p><span>{{ posts.length }} {{ tr("news.updates") }}</span></div>
    <div class="news-feed">
      <article v-for="(post, index) in posts" :key="post.media_post_id" class="news-story">
        <img :src="postImage(post.image_url, index)" alt="">
        <div>
          <p class="story-meta"><span>{{ tr("news.published") }}</span>{{ new Date(post.published_at).toLocaleDateString(tr("locale.code"), { dateStyle: 'long' }) }}</p>
          <h2>{{ post.title }}</h2>
          <p class="story-excerpt">{{ post.excerpt }}</p>
          <p class="story-body">{{ post.body }}</p>
        </div>
      </article>
      <div v-if="!loading && !posts.length" class="empty-state"><strong>{{ tr("news.empty.title") }}</strong><p>{{ tr("news.empty.text") }}</p></div>
    </div>
  </main>
</template>
