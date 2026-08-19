<script setup>
defineProps({ t: { type: Object, required: true }, showMain: Boolean, showBack: Boolean });
defineEmits(["main", "back"]);
</script>

<template>
  <aside class="demo-rail">
    <a class="rail-exit" href="/dashboard/demo/">
      <span>↗</span>{{ t.exit }}
    </a>
    <div class="rail-mark" aria-hidden="true">UMST</div>
    <div class="rail-bottom">
      <button v-if="showBack" type="button" @click="$emit('back')">← {{ t.back }}</button>
      <button v-if="showMain" type="button" @click="$emit('main')">⌂ {{ t.mainMenu }}</button>
    </div>
  </aside>
</template>
