<template>
  <section class="home-user-card">
    <img src="/images/Chris.jpg" alt="profile" />
    <div class="home-user-name">{{ user.username }}</div>
    <div class="home-user-alias">{{ user.alias }}</div>
    <p>{{ user.description }}</p>
    <router-link to="/dashboard/profile">
      {{ t('dashboard.title') }}
    </router-link>
  </section>
</template>

<script setup>
import { useUser } from '@/composables/useUser'
import { useI18n } from '@/composables/useI18n'

const { user } = useUser()
const { t } = useI18n()
</script>