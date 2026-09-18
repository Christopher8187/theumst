<script setup lang="ts">
defineProps<{ images: { source_image_id: string | number; semantic_context_name?: string; url?: string }[]; label: string }>();
defineEmits(['open-image']);
</script>

<template>
  <span class="notebook-image-links">
    <a v-for="image in images" :key="image.source_image_id" :href="image.url || '#'" @click.prevent="$emit('open-image', image)">▧ {{ image.semantic_context_name || `${label} ${image.source_image_id}` }}</a>
  </span>
</template>

<style scoped>
.notebook-image-links{display:inline;margin-inline-start:.4em}
.notebook-image-links a{display:inline;padding:0;margin:0 .4em 0 0;border:0;background:none;color:#bfdce2;font:inherit;line-height:inherit;vertical-align:baseline;text-decoration:underline;text-underline-offset:3px;cursor:pointer}
</style>
