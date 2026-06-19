<template>
  <header class="top">
    <div class="brand">
      <router-link to="/">
        <img class="logo" src="/images/logo.png" :alt="t('alt.logo')">
      </router-link>
      <h1>{{ t('brand.title') }}</h1>
    </div>

    <nav class="nav">
      <router-link to="/">{{ t('nav.home') }}</router-link>
      <router-link to="/news">{{ t('nav.news') }}</router-link>
      <router-link to="/about">{{ t('nav.about') }}</router-link>
      <router-link to="/wiki">{{ t('nav.wiki') }}</router-link>

      <router-link v-if="!user" to="/login">
        {{ t('nav.login') }}
      </router-link>

      <router-link class="get" to="/get">
        {{ t('nav.get') }}
      </router-link>

      <LanguageSwitcher />
    </nav>

    <UserCard v-if="user" />
  </header>
</template>

<script setup>
import { useI18n } from '@/utils/useI18n'
import { useUser } from '@/utils/useUser'
import LanguageSwitcher from './LanguageSwitcher.vue'
import UserCard from './UserCard.vue'

const { t } = useI18n()
const { user } = useUser()
</script>