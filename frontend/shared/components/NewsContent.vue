<script setup lang="ts">
import { ref, watch } from "vue";
import { apiFetch, apiUrl } from "../../urls.js";
const props = defineProps<{
  labels: Record<string, string>;
  language: string;
  slug?: string;
  open: boolean;
}>();
const emit = defineEmits<{ subscriptions: []; article: [slug: string] }>();
const posts = ref<any[]>([]),
  loading = ref(false),
  error = ref(""),
  section = ref("news");
let requestId = 0;
async function load() {
  const id = ++requestId,
    slug = props.slug;
  loading.value = true;
  error.value = "";
  try {
    const response = await apiFetch(
      slug ? "/api/news/" + encodeURIComponent(slug) : "/api/news",
    );
    if (!response.ok) throw Error(props.labels.loadError);
    const data = await response.json();
    if (id === requestId) posts.value = slug ? [data.post] : data.posts;
  } catch (e: any) {
    if (id === requestId) error.value = e.message;
  } finally {
    if (id === requestId) loading.value = false;
  }
}
watch(
  () => [props.slug, props.open],
  () => {
    if (props.open) {
      section.value = "news";
      load();
    }
  },
  { immediate: true },
);
function imageUrl(value: string) {
  return /^https?:\/\//.test(value) ? value : apiUrl(value);
}
</script>
<template>
  <nav class="editorial-tabs" :aria-label="labels.news">
    <button :class="{ active: section === 'news' }" @click="section = 'news'">
      {{ labels.news }}</button
    ><button
      :class="{ active: section === 'safety' }"
      @click="section = 'safety'"
    >
      {{ labels.safety }}
    </button>
  </nav>
  <div class="page-content">
    <template v-if="section === 'news'"
      ><div class="news-header">
        <h2>{{ labels.news }}</h2>
        <button class="quiet-link" @click="emit('subscriptions')">
          {{ labels.updates }} ↗
        </button>
      </div>
      <p v-if="loading">{{ labels.loading }}</p>
      <div v-else-if="error" role="alert">
        {{ error }} <button @click="load">{{ labels.retry }}</button>
      </div>
      <template v-else
        ><p v-if="!posts.length">
          {{
            language === "zh"
              ? "暂无新闻。"
              : language === "ja"
                ? "ニュースはまだありません。"
                : "No news yet."
          }}
        </p>
        <article
          v-for="post in posts"
          :key="post.media_post_id"
          class="news-story"
          :id="post.slug"
        >
          <small>{{
            new Date(post.published_at).toLocaleDateString(language)
          }}</small>
          <h3>
            <a
              :href="'/news/' + encodeURIComponent(post.slug)"
              @click.prevent="emit('article', post.slug)"
              >{{ post.title }}</a
            >
          </h3>
          <p class="lede">{{ post.excerpt }}</p>
          <img
            v-if="post.image_url"
            :src="imageUrl(post.image_url)"
            alt=""
            loading="lazy"
          />
          <p class="story-body">{{ post.body }}</p>
        </article></template
      ></template
    ><template v-else
      ><div class="kicker">{{ labels.safety }}</div>
      <h2>
        {{
          language === "zh"
            ? "理解模型所理解的。"
            : language === "ja"
              ? "モデルの理解を理解する。"
              : "Understand what a model understands."
        }}
      </h2>
      <p>
        {{
          language === "zh"
            ? "结构化知识让我们可以更精确地探讨 AI 的能力与局限。研究介绍和项目笔记将发布于此。"
            : language === "ja"
              ? "構造化された知識を通じて、AIの能力と限界をより正確に問い直します。研究紹介とプロジェクトの記録をここに掲載します。"
              : "Structured knowledge gives us a way to ask more precise questions about AI capabilities and limitations. Research introductions and project notes will appear here."
        }}
      </p></template
    >
  </div>
</template>
