<script setup>
defineProps({
  t: { type: Object, required: true },
  keys: { type: Array, required: true },
  output: String,
  outputError: Boolean
});

defineEmits(["create", "revoke"]);
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

    <div class="key-list">
      <article v-for="key in keys" :key="key.api_key_id" class="key-row" :class="{ revoked: key.revoked_at }">
        <div>
          <h3>{{ key.name }}</h3>
          <p>{{ key.key_prefix }}… {{ key.revoked_at ? t.revoked : t.active }}</p>
        </div>
        <button v-if="!key.revoked_at" @click="$emit('revoke', key.api_key_id)">{{ t.revoke }}</button>
      </article>
    </div>
  </section>
</template>
