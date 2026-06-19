<script setup>
defineProps({
  t: { type: Object, required: true },
  lang: { type: String, required: true },
  translateSrc: { type: String, required: true }
});

defineEmits(["close", "choose"]);
</script>

<template>
  <div class="language-modal-backdrop" @click.self="$emit('close')">
    <section class="language-modal">
      <button class="modal-close" @click="$emit('close')">×</button>
      <img class="modal-language-icon" :src="translateSrc" alt="">
      <h2>{{ t.chooseLanguage }}</h2>
      <p>{{ t.chooseLanguageText }}</p>

      <button class="language-option" :class="{ active: lang === 'en' }" @click="$emit('choose', 'en')">English</button>
      <button class="language-option" :class="{ active: lang === 'zh' }" @click="$emit('choose', 'zh')">中文</button>
      <button class="language-option" :class="{ active: lang === 'ja' }" @click="$emit('choose', 'ja')">日本語</button>
    </section>
  </div>
</template>
