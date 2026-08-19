<script setup>
import { ref } from "vue";

const props = defineProps({
  t: { type: Object, required: true },
  profile: { type: Object, required: true },
  message: String,
  emailChangeMessage: String,
  emailChangeError: Boolean
});
const emit = defineEmits(["save", "change-email"]);
const newEmail = ref("");
const currentPassword = ref("");

function authorityLabel(value) {
  const key = { user: "roleUser", betatester: "roleBetatester", manager: "roleManager" }[value] || "roleStaff";
  return props.t[key] || props.t.roleStaff;
}

function requestEmailChange() {
  emit("change-email", { new_email: newEmail.value, current_password: currentPassword.value });
  currentPassword.value = "";
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
      <label>{{ t.email }}<input v-model="profile.email" type="email" readonly></label>
      <label>{{ t.alias }}<input v-model="profile.alias"></label>
      <label>{{ t.description }}<textarea v-model="profile.description" rows="5"></textarea></label>
      <button type="submit">{{ t.saveProfile }}</button>
      <p class="message">{{ message }}</p>
    </form>

    <section class="email-change-panel">
      <div>
        <p class="eyebrow">{{ t.accountSecurity }}</p>
        <h2>{{ t.changeEmail }}</h2>
        <p class="muted">{{ t.changeEmailText }}</p>
      </div>
      <form class="dashboard-form" @submit.prevent="requestEmailChange">
        <label>{{ t.newEmail }}<input v-model="newEmail" type="email" autocomplete="email" required></label>
        <label>{{ t.currentPassword }}<input v-model="currentPassword" type="password" autocomplete="current-password" required></label>
        <button type="submit">{{ t.sendEmailChange }}</button>
        <p v-if="emailChangeMessage" class="message key-output" :class="{ error: emailChangeError }">{{ emailChangeMessage }}</p>
      </form>
    </section>
  </section>
</template>
