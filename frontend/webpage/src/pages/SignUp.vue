<template>
  <HeaderNav />

  <main class="login-page">
    <section class="login-shell">
      <!-- 左侧文案 -->
      <div class="login-copy">
        <div class="login-orb"></div>
        <p class="login-kicker">{{ t('signup.kicker') }}</p>
        <h2>{{ t('signup.heading') }}</h2>
        <p>{{ t('signup.note') }}</p>
      </div>

      <!-- 注册卡片 -->
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
            <input v-model="form.username" type="text" autocomplete="username" required />
          </label>

          <label>
            <span>{{ t('signup.email') }}</span>
            <input v-model="form.email" type="email" autocomplete="email" required />
          </label>

          <label>
            <span>{{ t('signup.password') }}</span>
            <input v-model="form.password" type="password" autocomplete="new-password" required />
          </label>

          <button type="submit">{{ t('signup.submit') }}</button>

          <router-link class="secondary-action" to="/login">
            {{ t('signup.login') }}
          </router-link>
        </form>
      </section>
    </section>
  </main>
</template>