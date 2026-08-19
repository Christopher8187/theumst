<script setup>
import { onMounted, ref } from "vue";
import { apiFetch, apiUrl, assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean });
const emit = defineEmits(["navigate", "set-language", "login", "signup"]);
const posts = ref([]);

function go(path) {
  emit("navigate", path);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function postImage(value, index) {
  if (!value) return assetUrl(index % 2 ? "graph.jpg" : "cave.jpg");
  return /^https?:\/\//.test(value) ? value : apiUrl(value);
}

onMounted(async () => {
  try {
    const res = await apiFetch("/api/news");
    if (res.ok) posts.value = (await res.json()).posts.slice(0, 3);
  } catch {
    posts.value = [];
  }
});
</script>

<template>
  <SiteHeader
    :tr="tr"
    show-user-card
    :session="session"
    @navigate="go"
    @set-language="$emit('set-language', $event)"
  />

  <main>
    <section class="home-hero site-container">
      <div class="hero-copy">
        <p class="hero-kicker"><span></span>{{ tr("home.kicker") }}</p>
        <h1>{{ tr("home.heading") }}</h1>
        <p class="hero-lead">{{ tr("home.lead") }}</p>
        <div class="hero-actions">
          <a href="/signup" class="primary-cta" @click.prevent="go('/signup')">{{ tr("home.cta.primary") }} <span>↗</span></a>
          <a href="#ecosystem" class="secondary-cta">{{ tr("home.cta.secondary") }} <span>↓</span></a>
        </div>
        <div class="trust-line">
          <span>{{ tr("home.trust.structured") }}</span>
          <span>{{ tr("home.trust.reviewed") }}</span>
          <span>{{ tr("home.trust.measurable") }}</span>
        </div>
      </div>

      <div class="hero-world" :aria-label="tr('alt.world')">
        <img :src="assetUrl('cave.jpg')" :alt="tr('alt.cave')">
        <div class="world-vignette"></div>
        <div class="world-status">
          <span class="live-pulse"></span>
          <div><small>{{ tr("home.world.status") }}</small><strong>{{ tr("home.world.title") }}</strong></div>
        </div>
        <div class="world-objective">
          <span>01</span>
          <div><small>{{ tr("home.world.objective") }}</small><strong>{{ tr("home.world.quest") }}</strong></div>
        </div>
        <div class="world-node node-one"><span></span>{{ tr("home.world.node1") }}</div>
        <div class="world-node node-two"><span></span>{{ tr("home.world.node2") }}</div>
      </div>
    </section>

    <section class="signal-strip">
      <div class="site-container signal-grid">
        <article><strong>1</strong><span>{{ tr("home.signal.source") }}</span></article>
        <div>→</div>
        <article><strong>2</strong><span>{{ tr("home.signal.structure") }}</span></article>
        <div>→</div>
        <article><strong>3</strong><span>{{ tr("home.signal.experience") }}</span></article>
        <div>→</div>
        <article><strong>4</strong><span>{{ tr("home.signal.training") }}</span></article>
      </div>
    </section>

    <section id="ecosystem" class="ecosystem-section site-container">
      <div class="section-intro">
        <p class="section-kicker">{{ tr("home.ecosystem.kicker") }}</p>
        <h2>{{ tr("home.ecosystem.heading") }}</h2>
        <p>{{ tr("home.ecosystem.lead") }}</p>
      </div>
      <div class="ecosystem-grid">
        <article class="ecosystem-card card-game">
          <span class="card-number">01</span>
          <div class="card-icon">✦</div>
          <h3>{{ tr("home.ecosystem.game.title") }}</h3>
          <p>{{ tr("home.ecosystem.game.text") }}</p>
          <span class="card-link">{{ tr("home.ecosystem.game.tag") }}</span>
        </article>
        <article class="ecosystem-card card-data">
          <span class="card-number">02</span>
          <div class="card-icon">⌘</div>
          <h3>{{ tr("home.ecosystem.data.title") }}</h3>
          <p>{{ tr("home.ecosystem.data.text") }}</p>
          <span class="card-link">{{ tr("home.ecosystem.data.tag") }}</span>
        </article>
        <article class="ecosystem-card card-safety">
          <span class="card-number">03</span>
          <div class="card-icon">◈</div>
          <h3>{{ tr("home.ecosystem.safety.title") }}</h3>
          <p>{{ tr("home.ecosystem.safety.text") }}</p>
          <span class="card-link">{{ tr("home.ecosystem.safety.tag") }}</span>
        </article>
      </div>
    </section>

    <section class="graph-section">
      <div class="site-container graph-layout">
        <div class="graph-visual">
          <img :src="assetUrl('graph.jpg')" :alt="tr('alt.graph')">
          <div class="graph-caption"><span>{{ tr("home.graph.caption") }}</span><strong>{{ tr("home.graph.live") }}</strong></div>
        </div>
        <div class="graph-copy">
          <p class="section-kicker">{{ tr("home.graph.kicker") }}</p>
          <h2>{{ tr("home.graph.heading") }}</h2>
          <p>{{ tr("home.graph.text") }}</p>
          <ol class="review-steps">
            <li><span>01</span><div><strong>{{ tr("home.graph.step1.title") }}</strong><p>{{ tr("home.graph.step1.text") }}</p></div></li>
            <li><span>02</span><div><strong>{{ tr("home.graph.step2.title") }}</strong><p>{{ tr("home.graph.step2.text") }}</p></div></li>
            <li><span>03</span><div><strong>{{ tr("home.graph.step3.title") }}</strong><p>{{ tr("home.graph.step3.text") }}</p></div></li>
          </ol>
        </div>
      </div>
    </section>

    <section class="news-preview site-container">
      <div class="section-heading-row">
        <div><p class="section-kicker">{{ tr("home.news.kicker") }}</p><h2>{{ tr("home.news.heading") }}</h2></div>
        <a href="/news" @click.prevent="go('/news')">{{ tr("home.news.all") }} →</a>
      </div>
      <div class="news-grid">
        <article v-for="(post, index) in posts" :key="post.media_post_id" class="news-card">
          <img :src="postImage(post.image_url, index)" alt="">
          <div class="news-card-copy">
            <span>{{ new Date(post.published_at).toLocaleDateString(tr("locale.code")) }}</span>
            <h3>{{ post.title }}</h3>
            <p>{{ post.excerpt || post.body }}</p>
          </div>
        </article>
        <article v-if="!posts.length" class="news-card news-empty">
          <div class="news-card-copy"><span>{{ tr("home.news.coming") }}</span><h3>{{ tr("home.news.emptyTitle") }}</h3><p>{{ tr("home.news.emptyText") }}</p></div>
        </article>
      </div>
    </section>

    <section class="final-cta site-container">
      <div><p class="section-kicker">{{ tr("home.final.kicker") }}</p><h2>{{ tr("home.final.heading") }}</h2></div>
      <a href="/signup" class="primary-cta" @click.prevent="go('/signup')">{{ tr("home.final.cta") }} <span>↗</span></a>
    </section>
  </main>

</template>
