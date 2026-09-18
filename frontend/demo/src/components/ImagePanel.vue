<script setup>
defineProps({ t:Object,image: Object, node: Object, downloadImage: Boolean });
defineEmits(["close"]);
</script>

<template>
  <section class="image-panel">
    <header>
      <div>
        <p>{{ t.bookImage }}</p>
        <h2>{{ image?.semantic_context_name || `Image ${image?.source_image_id || ''}` }}</h2>
      </div>
      <button type="button" :aria-label="t.close" @click="$emit('close')">×</button>
    </header>
    <div class="image-stage">
      <img v-if="image?.url" :src="image.url" :alt="image.semantic_context_name || `Book image ${image.source_image_id}`">
      <p v-else>{{ t.imageUnavailable }}</p>
    </div>
    <footer>
      <span v-if="node">{{ node.label || node.type }}</span>
      <small v-if="image?.metadata?.context">{{ image.metadata.context }}</small>
      <a v-if="image?.url" :href="image.url" :target="downloadImage?undefined:'_blank'" :download="downloadImage?'book-image-'+image.source_image_id:undefined" rel="noreferrer">{{ downloadImage?t.download:t.openOriginal }} {{downloadImage?'↓':'↗'}}</a>
    </footer>
  </section>
</template>
