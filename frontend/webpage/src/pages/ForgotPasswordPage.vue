<script setup>
import { ref } from "vue";
import { apiFetch } from "../../../urls.js";

defineProps({ tr: Function, session: Object });
defineEmits(["navigate", "set-language"]);

const email = ref("");
const state = ref("idle");
const message = ref("");

async function submit() {
  state.value = "sending";
  message.value = "";
  try {
    const response = await apiFetch("/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: email.value })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Password recovery is temporarily unavailable.");
    state.value = "success";
    message.value = data.detail;
  } catch (error) {
    state.value = "error";
    message.value = error.message;
  }
}
</script>

<template>

  <main class="login-page">
    <section class="login-shell">
      <div class="login-copy">
        <div class="login-orb"></div>
        <p class="login-kicker">{{ tr("forgot.kicker") }}</p>
        <h2>{{ tr("forgot.heading") }}</h2>
        <p>{{ tr("forgot.note") }}</p>
      </div>

      <section class="login-card">
        <div class="login-card-top">
          <div>
            <p>{{ tr("forgot.title") }}</p>
            <h2>{{ tr("forgot.cardHeading") }}</h2>
          </div>
        </div>

        <p v-if="message" class="login-status" :class="state === 'success' ? 'is-success' : 'is-error'">{{ message }}</p>

        <form v-if="state !== 'success'" @submit.prevent="submit">
          <label>
            <span>{{ tr("forgot.email") }}</span>
            <input v-model.trim="email" type="email" autocomplete="email" required>
          </label>
          <button type="submit" :disabled="state === 'sending'">{{ state === "sending" ? tr("forgot.sending") : tr("forgot.submit") }}</button>
          <a class="secondary-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("forgot.back") }}</a>
        </form>

        <a v-else class="secondary-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("forgot.back") }}</a>
      </section>
    </section>
  </main>
</template>
