<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  t: { type: Object, required: true },
  users: { type: Array, required: true },
  loading: Boolean,
  message: String,
  error: Boolean
});
defineEmits(["refresh"]);

const query = ref("");
const visibleUsers = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return props.users;
  return props.users.filter((user) => [user.username, user.email, user.alias]
    .some((value) => String(value || "").toLowerCase().includes(needle)));
});

function accountLabel(value) {
  const key = {
    user: "roleUser",
    betatester: "roleBetatester",
    manager: "roleManager",
    staff: "roleStaff"
  }[value];
  return props.t[key] || props.t.roleStaff;
}

function localDate(value) {
  return value ? new Date(value).toLocaleString(props.t.dateLocale) : props.t.never;
}
</script>

<template>
  <section class="dashboard-card wide-card users-page">
    <header class="workspace-head">
      <div>
        <p class="eyebrow">{{ t.accountOperations }}</p>
        <h1>{{ t.usersTitle }}</h1>
        <p class="muted">{{ t.usersText }}</p>
      </div>
      <button class="quiet-button" type="button" @click="$emit('refresh')">{{ t.refresh }}</button>
    </header>

    <div class="workspace-stats">
      <article><strong>{{ users.length }}</strong><span>{{ t.totalAccounts }}</span></article>
      <article><strong>{{ users.filter(user => user.demo_status === 'pending').length }}</strong><span>{{ t.pendingDemoRequests }}</span></article>
      <article><strong>{{ users.reduce((sum, user) => sum + Number(user.active_api_keys || 0), 0) }}</strong><span>{{ t.activeApiKeys }}</span></article>
    </div>

    <div class="user-search">
      <label>
        <span>{{ t.searchAccounts }}</span>
        <input v-model="query" type="search" :placeholder="t.searchAccountsPlaceholder">
      </label>
      <span>{{ visibleUsers.length }} {{ t.results }}</span>
    </div>

    <p v-if="message" class="message key-output" :class="{ error }">{{ message }}</p>
    <div v-if="loading" class="dashboard-loading">{{ t.usersLoading }}</div>
    <div v-else-if="visibleUsers.length" class="users-table-wrap" tabindex="0" role="region" :aria-label="t.usersTitle">
      <table class="users-table">
        <thead>
          <tr>
            <th>{{ t.account }}</th>
            <th>{{ t.accountType }}</th>
            <th>{{ t.apiKeys }}</th>
            <th>{{ t.demoAccess }}</th>
            <th>{{ t.lastSession }}</th>
            <th>{{ t.joined }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in visibleUsers" :key="user.user_id">
            <td>
              <div class="user-identity">
                <span>{{ String(user.username || '?').slice(0, 1).toUpperCase() }}</span>
                <div><strong>{{ user.alias || user.username }}</strong><small>@{{ user.username }} · {{ user.email }}</small></div>
              </div>
            </td>
            <td><span class="account-type-chip">{{ accountLabel(user.account_type) }}</span></td>
            <td>{{ user.active_api_keys }}</td>
            <td>{{ user.demo_status || t.notRequested }}</td>
            <td>{{ localDate(user.last_session_at) }}</td>
            <td>{{ localDate(user.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="content-empty"><strong>{{ t.noUsers }}</strong><p>{{ t.noUsersText }}</p></div>
  </section>
</template>
