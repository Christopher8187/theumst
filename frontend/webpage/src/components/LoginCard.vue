<template>
  <section class="login-card">
    <div class="login-card-top">
      <img src="/images/logo.png" :alt="t('alt.logo')" />
      <div>
        <p>{{ t('signup.title') }}</p>
        <h2>{{ t('signup.cardHeading') }}</h2>
      </div>
    </div>

    <form @submit.prevent="onSubmit">
      <label>
        <span>{{ t('signup.username') }}</span>
        <input
          v-model="form.username"
          type="text"
          name="username"
          autocomplete="username"
          required
        />
      </label>

      <label>
        <span>{{ t('signup.email') }}</span>
        <input
          v-model="form.email"
          type="email"
          name="email"
          autocomplete="email"
          required
        />
      </label>

      <label>
        <span>{{ t('signup.password') }}</span>
        <input
          v-model="form.password"
          type="password"
          name="password"
          autocomplete="new-password"
          required
        />
      </label>

      <button type="submit">{{ t('signup.submit') }}</button>

      <RouterLink class="secondary-action" to="/login">
        {{ t('signup.login') }}
      </RouterLink>
    </form>
  </section>
</template>

<script setup>
import { reactive } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const router = useRouter()

const form = reactive({
  username: '',
  email: '',
  password: ''
})

const onSubmit = async () => {
  // ✅ 替代原来的 form action
  await fetch('/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form)
  })

  router.push('/login')
}
</script>