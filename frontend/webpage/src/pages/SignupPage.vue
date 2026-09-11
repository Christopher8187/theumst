<script setup>


defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean, loginMessage: String, authBusy: Boolean });
defineEmits(["navigate", "set-language", "signup"]);
</script>

<template>

  <main class="login-page">
    <section class="login-shell">
      <div class="login-copy">
        <div class="login-orb"></div>
        <p class="login-kicker">{{ tr("signup.kicker") }}</p>
        <h2>{{ tr("signup.heading") }}</h2>
        <p>{{ tr("signup.note") }}</p>
      </div>

      <section class="login-card">
        <div class="login-card-top">
          <div>
            <p>{{ tr("signup.title") }}</p>
            <h2>{{ tr("signup.cardHeading") }}</h2>
          </div>
        </div>

        <p v-if="loginMessage" class="login-status is-error" role="alert">{{loginMessage}}</p>
        <form @submit.prevent="$emit('signup', $event)">
          <label>
            <span>{{ tr("signup.username") }}</span>
            <input type="text" name="username" autocomplete="username" required>
          </label>

          <label>
            <span>{{ tr("signup.email") }}</span>
            <input type="email" name="email" autocomplete="email" required>
          </label>

          <label>
            <span>{{ tr("signup.password") }}</span>
            <input type="password" name="password" autocomplete="new-password" required>
          </label>

          <button type="submit" :disabled="authBusy">{{ tr("signup.submit") }}</button>
          <p class="auth-form-note">{{ tr("signup.verifyNote") }}</p>
          <a class="secondary-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("signup.login") }}</a>
        </form>
      </section>
    </section>
  </main>
</template>
