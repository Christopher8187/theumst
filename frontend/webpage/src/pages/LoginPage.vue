<script setup>
import { assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean });
defineEmits(["navigate", "set-language", "login"]);
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
        <p class="login-kicker">{{ tr("login.kicker") }}</p>
        <h2>{{ tr("login.heading") }}</h2>
        <p>{{ tr("login.note") }}</p>
      </div>

      <section class="login-card">
        <div class="login-card-top">
          <img :src="assetUrl('logo.png')" :alt="tr('alt.logo')">
          <div>
            <p>{{ tr("login.title") }}</p>
            <h2>{{ tr("login.cardHeading") }}</h2>
          </div>
        </div>

        <p v-if="loginError" class="login-error">{{ tr("login.badLogin") }}</p>

        <form @submit.prevent="$emit('login', $event)">
          <label>
            <span>{{ tr("login.username") }}</span>
            <input type="text" name="username" autocomplete="username" required>
          </label>

          <label>
            <span>{{ tr("login.password") }}</span>
            <input type="password" name="password" autocomplete="current-password" required>
          </label>

          <button type="submit">{{ tr("login.submit") }}</button>
          <a class="secondary-action" href="/signup" @click.prevent="$emit('navigate', '/signup')">{{ tr("login.signup") }}</a>
        </form>
      </section>
    </section>
  </main>
</template>
