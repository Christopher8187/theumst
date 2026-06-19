<template>
  <header class="top login-top">
    <div class="brand">
      <a href="/">
        <img class="logo" src="@/assets/images/logo.png" :alt="$t('alt.logo')" />
      </a>
      <h1>{{ $t('brand.title') }}</h1>
    </div>

    <nav class="nav">
      <a href="/">{{ $t('nav.home') }}</a>
      <a href="/news">{{ $t('nav.news') }}</a>
      <a href="/about">{{ $t('nav.about') }}</a>
      <a href="/wiki">{{ $t('nav.wiki') }}</a>
      <a href="/login">{{ $t('nav.login') }}</a>
      <a class="get" href="/get">{{ $t('nav.get') }}</a>

      <LanguageMenu />
    </nav>
  </header>
</template>

<h2 class="hero-title">{{ $t('news.title') }}</h2>

<script setup>
import LanguageMenu from './LanguageMenu.vue'
</script>