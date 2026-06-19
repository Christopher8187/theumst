<template>
  <section :class="['feature', reverse && 'reverse']">
    <img :src="image" :alt="t(altKey)" />
    <div class="text">
      <h2>{{ t(titleKey) }}</h2>
      <p>{{ t(textKey) }}</p>
    </div>
  </section>
</template>

<script setup>
defineProps({
  image: String,
  altKey: String,
  titleKey: String,
  textKey: String,
  reverse: Boolean
})
</script>