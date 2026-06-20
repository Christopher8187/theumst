<script setup>
import { assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean });
defineEmits(["navigate", "set-language", "signup"]);
</script>

<template>
  <SiteHeader
    :tr="tr"
    compact
    :session="session"
    @navigate="$emit('navigate', $event)"
    @set-language="$emit('set-language', $event)"
  />

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
          <img :src="assetUrl('logo.png')" :alt="tr('alt.logo')">
          <div>
            <p>{{ tr("signup.title") }}</p>
            <h2>{{ tr("signup.cardHeading") }}</h2>
          </div>
        </div>

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

          <button type="submit">{{ tr("signup.submit") }}</button>
          <a class="secondary-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("signup.login") }}</a>
        </form>
      </section>
    </section>
  </main>
</template>
