<script setup>
defineProps({ html: { type: String, required: true } });
defineEmits(["page-click", "page-submit"]);
</script>

<template>
  <div v-html="html" @click="$emit('page-click', $event)" @submit="$emit('page-submit', $event)"></div>
</template>
