<script setup>
defineProps({ image: Object, node: Object });
defineEmits(["close"]);
</script>

<template>
  <section class="image-panel">
    <header>
      <div>
        <p>Book image</p>
        <h2>{{ image?.semantic_context_name || `Image ${image?.source_image_id || ''}` }}</h2>
      </div>
      <button type="button" aria-label="Close image" @click="$emit('close')">×</button>
    </header>
    <div class="image-stage">
      <img v-if="image?.url" :src="image.url" :alt="image.semantic_context_name || `Book image ${image.source_image_id}`">
      <p v-else>Image unavailable.</p>
    </div>
    <footer>
      <span v-if="node">From {{ node.label || node.type }}</span>
      <small v-if="image?.metadata?.context">{{ image.metadata.context }}</small>
      <a v-if="image?.url" :href="image.url" target="_blank" rel="noreferrer">Open original ↗</a>
    </footer>
  </section>
</template>
