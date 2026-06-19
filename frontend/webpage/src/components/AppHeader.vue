<template>
  <header class="top">
    <div class="brand">
      <RouterLink to="/">
        <img class="logo" src="/images/logo.png" :alt="t('alt.logo')" />
      </RouterLink>
      <h1>{{ t('brand.title') }}</h1>
    </div>

    <nav class="nav">
      <RouterLink to="/">{{ t('nav.home') }}</RouterLink>
      <RouterLink to="/news">{{ t('nav.news') }}</RouterLink>
      <RouterLink to="/about">{{ t('nav.about') }}</RouterLink>
      <RouterLink to="/wiki">{{ t('nav.wiki') }}</RouterLink>
      <RouterLink to="/login">{{ t('nav.login') }}</RouterLink>
      <RouterLink to="/get" class="get">{{ t('nav.get') }}</RouterLink>

      <LanguageMenu />
    </nav>

    <h2 class="hero-title">{{ t('signup.title') }}</h2>
  </header>
</template>

<script setup>
import { useI18n } from '@/composables/useI18n'
import LanguageMenu from './LanguageMenu.vue'

const { t } = useI18n()
</script>
