<script setup>
const props = defineProps({ t: { type: Object, required: true }, profile: { type: Object, required: true }, message: String });
defineEmits(["save"]);

function authorityLabel(value) {
  const key = { user: "roleUser", manager: "roleManager", admin: "roleAdmin", superadmin: "roleSuperadmin" }[value];
  return props.t[key] || value;
}
</script>

<template>
  <section class="dashboard-card">
    <p class="eyebrow">{{ t.identity }}</p>
    <h1>{{ t.profileTitle }}</h1>
    <p class="muted">{{ t.profileText }}</p>

    <div class="readonly-field">
      <span>{{ t.authorityType }}</span>
      <strong>{{ authorityLabel(profile.authority_type) }}</strong>
    </div>

    <form class="dashboard-form" @submit.prevent="$emit('save')">
      <label>{{ t.username }}<input v-model="profile.username" required></label>
      <label>{{ t.email }}<input v-model="profile.email" type="email" required></label>
      <label>{{ t.alias }}<input v-model="profile.alias"></label>
      <label>{{ t.description }}<textarea v-model="profile.description" rows="5"></textarea></label>
      <button type="submit">{{ t.saveProfile }}</button>
      <p class="message">{{ message }}</p>
    </form>
  </section>
</template>
