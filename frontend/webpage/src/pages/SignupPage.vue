<template>
  <div class="login-page">
    <AppHeader />

    <section class="login-shell">
      <!-- 左侧文案 -->
      <div class="login-copy">
        <div class="login-orb"></div>
        <p class="login-kicker">{{ t('signup.kicker') }}</p>
        <h2>{{ t('signup.heading') }}</h2>
        <p>{{ t('signup.note') }}</p>
      </div>

      <!-- 右侧表单 -->
      <LoginCard />
    </section>
  </div>
</template>

<script setup>
import AppHeader from '@/components/AppHeader.vue'
import LoginCard from '@/components/LoginCard.vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
</script>