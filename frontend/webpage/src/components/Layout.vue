<template>
  <div :data-title="t('get.title')">
    <AppHeader />
    <main class="content empty">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
import { useI18n } from '@/composables/useI18n'

useI18n().setLocale('zh')
</script>