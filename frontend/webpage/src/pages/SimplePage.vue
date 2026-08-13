<script setup>
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, titleKey: String, session: Object, loginError: Boolean });
defineEmits(["navigate", "set-language", "login", "signup"]);
</script>

<template>
  <SiteHeader
    :tr="tr"
    :title-key="titleKey"
    :session="session"
    @navigate="$emit('navigate', $event)"
    @set-language="$emit('set-language', $event)"
  />
  <main class="site-container simple-page">
    <p class="section-kicker">{{ tr("brand.category") }}</p>
    <h2>{{ tr(titleKey) }}</h2>
    <p>{{ tr(titleKey.startsWith('wiki') ? 'wiki.intro' : titleKey.startsWith('get') ? 'get.intro' : '') }}</p>
  </main>
</template>
