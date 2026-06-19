<template>
  <div class="language-menu">
    <button class="language-button" @click.stop="open = !open">
      <img src="@/assets/images/translate.svg" alt="" />
      <span>{{ $t('language.label') }}</span>
    </button>

    <div class="language-dropdown" v-show="open">
      <button @click="changeLang('zh')">{{ $t('language.zh') }}</button>
      <button @click="changeLang('en')">{{ $t('language.en') }}</button>
      <button @click="changeLang('ja')">{{ $t('language.ja') }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const open = ref(false)
const { locale } = useI18n()

const changeLang = (lang) => {
  locale.value = lang
  localStorage.setItem('lang', lang)
  open.value = false
}
</script>