<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  t: { type: Object, required: true },
  keys: { type: Array, required: true },
  output: String,
  outputError: Boolean,
  // A key made by this page visit; its full text is shown only here, once.
  newKey: { type: Object, default: null }
});

defineEmits(["create", "revoke", "upgrade"]);

const copied = ref(false);
const keyText = ref(null);
watch(() => props.newKey, () => { copied.value = false; });

async function copyKey() {
  try {
    await navigator.clipboard.writeText(props.newKey.key);
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

function tierName(key) {
  return key.level_name === "standard" ? props.t.tierStandard : key.level_name;
}
</script>

<template>
  <section class="dashboard-card">
    <p class="eyebrow">{{ t.developer }}</p>
    <h1>{{ t.apiTitle }}</h1>
    <p class="muted">{{ t.apiText }}</p>

    <form class="dashboard-form small-form" @submit.prevent="$emit('create', $event)" novalidate>
      <label>{{ t.keyName }}<input name="name" autocomplete="off"></label>
      <button type="submit">{{ t.createKey }}</button>
    </form>

    <p class="message key-output" :class="{ error: outputError }" v-if="output">{{ output }}</p>

    <section v-if="newKey" class="new-key" aria-live="polite">
      <p v-if="newKey.isDefault" class="new-key-title">{{ t.defaultKeyMade }}</p>
      <p v-else class="new-key-title">{{ t.newKey }} <strong>{{ newKey.name }}</strong></p>
      <div class="new-key-value">
        <code ref="keyText">{{ newKey.key }}</code>
        <button type="button" @click="copyKey">{{ copied ? t.keyCopied : t.copyKey }}</button>
      </div>
      <p class="new-key-note">{{ t.keyShownOnce }}</p>
    </section>

    <div class="key-list">
      <article v-for="key in keys" :key="key.api_key_id" class="key-row" :class="{ revoked: key.revoked_at }">
        <div>
          <h3>{{ key.name }}</h3>
          <p>{{ key.key_prefix }}… · {{ key.key_type === 'master' ? t.masterKey : t.regularKey }} · {{ key.revoked_at ? t.revoked : t.active }}</p>
          <p v-if="key.key_type === 'regular' && key.requests_per_minute">{{ tierName(key) }} · {{ key.requests_per_minute }} {{ t.requestsPerMinute }}</p>
          <p v-if="key.key_type === 'master'">{{ t.unlimitedMaster }}</p>
        </div>
        <div class="key-actions">
          <button v-if="key.can_upgrade_to_master" @click="$emit('upgrade', key.api_key_id)">{{ t.upgradeMaster }}</button>
          <button v-if="!key.revoked_at" @click="$emit('revoke', key.api_key_id)">{{ t.revoke }}</button>
        </div>
      </article>
    </div>
  </section>
</template>
