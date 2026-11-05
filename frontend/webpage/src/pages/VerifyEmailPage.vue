<script setup>
import { ref, watch } from "vue";
import { apiFetch } from "../../../urls.js";

const props = defineProps({ tr: Function, session: Object, entryQuery: { type: String, default: "" } });
defineEmits(["navigate", "set-language"]);

const state = ref("idle");
const message = ref("");
const email = ref("");
// Confirming makes the account's Default key; its full text arrives once and
// stays only in this page's memory.
const defaultKey = ref(null);
const copied = ref(false);
const keyText = ref(null);

async function confirmToken(token, kind) {
  state.value = "loading";
  const endpoint = kind === "change" ? "/auth/email-change/confirm" : "/auth/email-verification/confirm";
  const res = await apiFetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token })
  });
  const data = await res.json().catch(() => ({}));
  state.value = res.ok ? "success" : "error";
  message.value = res.ok ? "" : (data.detail || "This confirmation link could not be used.");
  defaultKey.value = res.ok && data.default_key ? data.default_key : null;
  copied.value = false;
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(defaultKey.value.key);
    copied.value = true;
  } catch {
    // Without clipboard access, select the key so it can be copied by hand.
    const range = document.createRange();
    range.selectNodeContents(keyText.value);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }
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

watch(() => props.entryQuery, value => {
  const query = new URLSearchParams(value);
  const token = query.get("token");
  defaultKey.value = null;
  if (token) confirmToken(token, query.get("kind"));
  else if (query.get("sent") === "1") state.value = "sent";
  else if (query.get("delivery") === "failed") state.value = "error";
  else state.value = "idle";
}, { immediate: true });
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

        <section v-if="state === 'success' && defaultKey" class="default-key" aria-live="polite">
          <p class="login-status">{{ tr("verify.keyNote") }}</p>
          <code ref="keyText">{{ defaultKey.key }}</code>
          <button type="button" @click="copyKey">{{ copied ? tr("verify.keyCopied") : tr("verify.keyCopy") }}</button>
        </section>

        <a v-if="state === 'success'" class="secondary-action" href="/login?verified=success" @click.prevent="$emit('navigate', '/login?verified=success')">{{ tr("verify.login") }}</a>
        <form v-else @submit.prevent="resend">
          <label><span>{{ tr("signup.email") }}</span><input v-model="email" type="email" autocomplete="email" required></label>
          <button type="submit" :disabled="state === 'loading'">{{ tr("verify.resend") }}</button>
          <a class="text-action" href="/login" @click.prevent="$emit('navigate', '/login')">{{ tr("forgot.back") }}</a>
        </form>
      </section>
    </section>
  </main>
</template>
