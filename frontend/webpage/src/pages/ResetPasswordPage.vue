<script setup>
import { onMounted, ref } from "vue";
import { apiFetch, assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

const props = defineProps({ tr: Function, session: Object });
defineEmits(["navigate", "set-language"]);

const token = ref(new URLSearchParams(location.search).get("token") || "");
const password = ref("");
const confirmation = ref("");
const state = ref(token.value ? "idle" : "error");
const message = ref(token.value ? "" : "This reset link is incomplete or invalid.");

onMounted(() => {
  if (token.value) history.replaceState(null, "", "/reset-password");
});

async function submit() {
  if (password.value !== confirmation.value) {
    state.value = "error";
    message.value = props.tr("reset.mismatch");
    return;
  }

  state.value = "sending";
  message.value = "";
  try {
    const response = await apiFetch("/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ token: token.value, new_password: password.value })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || props.tr("reset.invalid"));
    state.value = "success";
    message.value = props.tr("reset.success");
  } catch (error) {
    state.value = "error";
    message.value = error.message;
  }
}
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
        <p class="login-kicker">{{ tr("reset.kicker") }}</p>
        <h2>{{ tr("reset.heading") }}</h2>
        <p>{{ tr("reset.note") }}</p>
      </div>

      <section class="login-card">
        <div class="login-card-top">
          <img :src="assetUrl('logo.png')" :alt="tr('alt.logo')">
          <div>
            <p>{{ tr("reset.title") }}</p>
            <h2>{{ tr("reset.cardHeading") }}</h2>
          </div>
        </div>

        <p v-if="message" class="login-status" :class="state === 'success' ? 'is-success' : 'is-error'">{{ message }}</p>

        <form v-if="state !== 'success' && token" @submit.prevent="submit">
          <label>
            <span>{{ tr("reset.password") }}</span>
            <input v-model="password" type="password" autocomplete="new-password" minlength="8" required>
          </label>
          <label>
            <span>{{ tr("reset.confirm") }}</span>
            <input v-model="confirmation" type="password" autocomplete="new-password" minlength="8" required>
          </label>
          <button type="submit" :disabled="state === 'sending'">{{ state === "sending" ? tr("reset.sending") : tr("reset.submit") }}</button>
        </form>

        <a class="secondary-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("reset.back") }}</a>
      </section>
    </section>
  </main>
</template>
