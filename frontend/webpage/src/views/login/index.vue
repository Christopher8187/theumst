<template>
  <div class="login-page">
    <Header />

    <section class="login-shell">
      <div class="login-copy">
        <div class="login-orb"></div>
        <p class="login-kicker">{{ $t('login.kicker') }}</p>
        <h2>{{ $t('login.heading') }}</h2>
        <p>{{ $t('login.note') }}</p>
      </div>

      <section class="login-card">
        <div class="login-card-top">
          <img src="@/assets/images/logo.png" :alt="$t('alt.logo')" />
          <div>
            <p>{{ $t('login.title') }}</p>
            <h2>{{ $t('login.cardHeading') }}</h2>
          </div>
        </div>

        <!-- 错误提示 -->
        <p v-if="showError" class="login-error">
          {{ $t('login.badLogin') }}
        </p>

        <form @submit.prevent="onSubmit">
          <label>
            <span>{{ $t('login.username') }}</span>
            <input
              v-model="form.username"
              type="text"
              autocomplete="username"
              required
            />
          </label>

          <label>
            <span>{{ $t('login.password') }}</span>
            <input
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              required
            />
          </label>

          <button type="submit">{{ $t('login.submit') }}</button>
          <a class="secondary-action" href="/signup">
            {{ $t('login.signup') }}
          </a>
        </form>
      </section>
    </section>
  </div>
</template>

<script setup>
import { reactive, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const form = reactive({
  username: '',
  password: ''
})

const showError = computed(
  () => route.query.error === 'bad-login'
)

const onSubmit = async () => {
  await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form)
  })
}
</script>

<style scoped>
/* 原 style.css 中 .login-page 相关样式 */
.login-page {}
.login-shell {}
.login-card {}
.login-error {
  color: #e53935;
}
</style>