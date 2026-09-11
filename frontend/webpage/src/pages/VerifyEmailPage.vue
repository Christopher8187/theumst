<script setup>
import { onMounted, ref } from "vue";
import { apiFetch } from "../../../urls.js";

defineProps({ tr: Function, session: Object });
defineEmits(["navigate", "set-language"]);

const state = ref("idle");
const message = ref("");
const email = ref("");

async function confirmToken(token) {
  state.value = "loading";
  const kind = new URLSearchParams(location.search).get("kind");
  const endpoint = kind === "change" ? "/auth/email-change/confirm" : "/auth/email-verification/confirm";
  const res = await apiFetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token })
  });
  const data = await res.json().catch(() => ({}));
  state.value = res.ok ? "success" : "error";
  message.value = res.ok ? "" : (data.detail || "This confirmation link could not be used.");
}

async function resend() {
  state.value = "loading";
  const res = await apiFetch("/auth/email-verification/resend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.value })
  });
  const data = await res.json().catch(() => ({}));
  state.value = res.ok ? "sent" : "error";
  message.value = data.detail || "Email confirmation is temporarily unavailable.";
}

onMounted(() => {
  const query = new URLSearchParams(location.search);
  const token = query.get("token");
  if (token) confirmToken(token);
  else if (query.get("sent") === "1") state.value = "sent";
  else if (query.get("delivery") === "failed") state.value = "error";
});
</script>

<template>
  <main class="login-page">
    <section class="login-shell verify-shell">
      <div class="login-copy">
        <div class="login-orb"></div>
        <p class="login-kicker">{{ tr("verify.kicker") }}</p>
        <h2>{{ tr("verify.heading") }}</h2>
        <p>{{ tr("verify.note") }}</p>
      </div>

      <section class="login-card">
        <div class="login-card-top">
          <div><p>{{ tr("verify.title") }}</p><h2>{{ tr("verify.cardHeading") }}</h2></div>
        </div>

        <p v-if="state === 'loading'" class="login-status">{{ tr("verify.checking") }}</p>
        <p v-else-if="state === 'success'" class="login-status is-success">{{ tr("verify.success") }}</p>
        <p v-else-if="state === 'sent'" class="login-status is-success">{{ tr("verify.sent") }}</p>
        <p v-else-if="state === 'error'" class="login-status is-error">{{ message || tr("verify.failed") }}</p>
        <p v-else class="login-status">{{ tr("verify.instructions") }}</p>

        <a v-if="state === 'success'" class="secondary-action" href="/login?verified=success">{{ tr("verify.login") }}</a>
        <form v-else @submit.prevent="resend">
          <label><span>{{ tr("signup.email") }}</span><input v-model="email" type="email" autocomplete="email" required></label>
          <button type="submit" :disabled="state === 'loading'">{{ tr("verify.resend") }}</button>
          <a class="text-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("forgot.back") }}</a>
        </form>
      </section>
    </section>
  </main>
</template>
