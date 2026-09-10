<script setup>
const props = defineProps({ t: Object, book: Object });
defineEmits(["realm", "grimoires"]);

const localAssetBase = String(import.meta.env.VITE_ASSET_BASE || "").replace(/\/$/, "");

function realmImage(filename) {
  return `${localAssetBase}/images/demo/${filename}`;
}

const realms = [
  ["text", "書", "realm-text.webp", "realmText"],
  ["notes", "寫", "realm-notes.webp", "realmNotes"],
  ["questions", "問", "realm-questions.webp", "realmQuestions"],
  ["expand", "道", "realm-expand.webp", "realmExpand"],
  ["review", "覺", "realm-review.webp", "realmReview"],
  ["preview", "天", "realm-preview.webp", "realmPreview"],
  ["advice", "意", "realm-advice.webp", "realmAdvice"],
  ["progress", "境", "realm-progress.webp", "realmProgress"]
];
</script>

<template>
  <section class="realm-view">
    <header class="realm-header view-pad">
      <div><p class="demo-kicker">{{ t.summonedGrimoire }}</p><h1>{{ book?.title }}</h1></div>
      <button class="ghost-button" type="button" @click="$emit('grimoires')">✦ {{ t.grimoires }}</button>
    </header>
    <div class="realm-grid">
      <button v-for="realm in realms" :key="realm[0]" type="button" class="realm-card" @click="$emit('realm', realm[0])">
        <img :src="realmImage(realm[2])" alt="">
        <span class="realm-character">{{ realm[1] }}</span>
        <div class="realm-copy"><p>{{ t[realm[0]] }}</p><small>{{ t[realm[3]] }}</small></div>
        <i>↗</i>
      </button>
    </div>
  </section>
</template>
