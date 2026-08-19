<script setup>
defineProps({ title: { type: String, required: true }, large: Boolean, progress: { type: Number, default: 0 } });
</script>

<template>
  <div class="book-object" :class="{ large }">
    <div class="book-spine"></div>
    <div class="book-sigil">∴</div>
    <strong>{{ title }}</strong>
    <div v-if="progress" class="book-progress"><span :style="{ width: `${progress}%` }"></span></div>
  </div>
</template>
