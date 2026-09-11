<script setup>

defineProps({ tr: Function, titleKey: String, session: Object, loginError: Boolean });
defineEmits(["navigate", "set-language", "login", "signup"]);
</script>

<template>
  <main class="site-container simple-page">
    <p class="section-kicker">{{ tr("brand.category") }}</p>
    <h2>{{ tr(titleKey) }}</h2>
    <p>{{ tr(titleKey.startsWith('wiki') ? 'wiki.intro' : titleKey.startsWith('get') ? 'get.intro' : '') }}</p>
  </main>
</template>
