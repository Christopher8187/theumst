<script setup>
import { assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean });
defineEmits(["navigate", "set-language"]);
</script>

<template>
  <SiteHeader
    :tr="tr"
    title-key="home.title"
    show-user-card
    :session="session"
    @navigate="$emit('navigate', $event)"
    @set-language="$emit('set-language', $event)"
  />

  <main class="content">
    <section class="feature">
      <img :src="assetUrl('cave.jpg')" :alt="tr('alt.cave')">
      <div class="text">
        <h2>{{ tr("home.explore.title") }}</h2>
        <p>{{ tr("home.explore.text") }}</p>
      </div>
    </section>

    <section class="feature reverse">
      <div class="text">
        <h2>{{ tr("home.learn.title") }}</h2>
        <p>{{ tr("home.learn.text") }}</p>
      </div>
      <img :src="assetUrl('graph.jpg')" :alt="tr('alt.graph')">
    </section>
  </main>
</template>
