<script setup>
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, titleKey: String, session: Object, loginError: Boolean });
defineEmits(["navigate", "set-language"]);
</script>

<template>
  <SiteHeader
    :tr="tr"
    :title-key="titleKey"
    :session="session"
    @navigate="$emit('navigate', $event)"
    @set-language="$emit('set-language', $event)"
  />
  <main class="content empty"></main>
</template>
