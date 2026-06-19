<script setup>
defineProps({ t: { type: Object, required: true }, superMessage: String, superError: Boolean });
const superUser = defineModel("superUser");
defineEmits(["make-admin"]);
</script>

<template>
  <section class="dashboard-card">
    <p class="eyebrow">{{ t.superadmin }}</p>
    <h1>{{ t.superadminTitle }}</h1>
    <p class="muted">{{ t.superadminText }}</p>

    <form class="dashboard-form small-form" @submit.prevent="$emit('make-admin')" novalidate>
      <label>{{ t.userToPromote }}<input v-model="superUser" autocomplete="off"></label>
      <button type="submit">{{ t.giveAdmin }}</button>
    </form>

    <p v-if="superMessage" class="message key-output" :class="{ error: superError }">{{ superMessage }}</p>
  </section>
</template>
