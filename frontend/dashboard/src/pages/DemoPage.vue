<script setup>
import { ref } from "vue";

const props = defineProps({
  t: { type: Object, required: true },
  access: { type: Object, default: null },
  requests: { type: Array, default: () => [] },
  loading: Boolean,
  message: { type: String, default: "" },
  error: Boolean,
  demoUrl: { type: String, required: true }
});
const emit = defineEmits(["request", "review", "refresh"]);
const requestMessage = ref("");

function sendRequest() {
  emit("request", requestMessage.value);
  requestMessage.value = "";
}

function accountTypeLabel(value) {
  const key = { user: "roleUser", betatester: "roleBetatester", manager: "roleManager", staff: "roleStaff" }[value];
  return props.t[key] || props.t.roleStaff;
}
</script>

<template>
  <section class="dashboard-card wide-card demo-access-page">
    <header class="workspace-head demo-access-head">
      <div>
        <p class="eyebrow">{{ t.demoProgram }}</p>
        <h1>{{ t.demoTitle }}</h1>
        <p class="muted">{{ t.demoText }}</p>
      </div>
      <span class="demo-version">Web Demo Version 0.1.0</span>
    </header>

    <div v-if="loading" class="dashboard-loading">{{ t.demoLoading }}</div>
    <template v-else-if="access">
      <div class="demo-gate-grid">
        <article class="demo-gate-card demo-hero-card">
          <div class="demo-orbit" aria-hidden="true"><span></span><span></span><i>UMST</i></div>
          <div>
            <p class="demo-status-label">{{ t.demoYourAccess }}</p>
            <h2>{{ access.can_enter ? t.demoReady : access.request?.status === 'pending' ? t.demoPending : t.demoLocked }}</h2>
            <p>{{ access.can_enter ? t.demoReadyText : access.request?.status === 'pending' ? t.demoPendingText : t.demoLockedText }}</p>
            <div class="demo-access-meta">
              <span>{{ t.accountType }}: <strong>{{ accountTypeLabel(access.account_type) }}</strong></span>
              <span v-if="access.request">{{ t.status }}: <strong>{{ access.request.status }}</strong></span>
            </div>
            <a v-if="access.can_enter" class="demo-enter-button" :href="demoUrl">{{ t.demoEnter }} <span>↗</span></a>
          </div>
        </article>

        <article v-if="!access.can_enter" class="demo-gate-card request-card">
          <p class="demo-status-label">{{ t.demoBetaAccess }}</p>
          <h2>{{ access.request?.status === 'pending' ? t.demoRequestReceived : t.demoRequestTitle }}</h2>
          <p>{{ access.request?.status === 'pending' ? t.demoRequestReceivedText : t.demoRequestText }}</p>
          <form v-if="access.request?.status !== 'pending'" class="dashboard-form" @submit.prevent="sendRequest">
            <label>{{ t.demoRequestMessage }}
              <textarea v-model="requestMessage" rows="4" :placeholder="t.demoRequestPlaceholder"></textarea>
            </label>
            <button type="submit">{{ access.request?.status === 'rejected' ? t.demoRequestAgain : t.demoRequestButton }}</button>
          </form>
          <div v-else class="pending-signal"><span></span>{{ t.demoAwaitingReview }}</div>
        </article>
      </div>

      <p v-if="message" class="message demo-message" :class="{ error }">{{ message }}</p>

      <section v-if="access.can_review" class="demo-review-panel">
        <div class="section-heading">
          <div><p class="eyebrow">{{ t.demoReviewQueue }}</p><h2>{{ t.demoAccessRequests }}</h2></div>
          <button class="quiet-button" type="button" @click="$emit('refresh')">{{ t.refresh }}</button>
        </div>
        <div class="review-stats">
          <article><strong>{{ requests.filter(item => item.status === 'pending').length }}</strong><span>{{ t.demoPendingCount }}</span></article>
          <article><strong>{{ requests.filter(item => item.status === 'approved').length }}</strong><span>{{ t.demoApprovedCount }}</span></article>
          <article><strong>{{ requests.length }}</strong><span>{{ t.demoTotalCount }}</span></article>
        </div>
        <div v-if="requests.length" class="demo-request-list">
          <article v-for="item in requests" :key="item.user_id" :class="`request-${item.status}`">
            <div class="request-identity"><span>{{ item.username.slice(0, 1).toUpperCase() }}</span><div><h3>{{ item.username }}</h3><p>{{ item.email }}</p></div></div>
            <p class="request-copy">{{ item.request_message || t.demoNoMessage }}</p>
            <div class="request-state"><span :class="item.status">{{ item.status }}</span><small>{{ new Date(item.requested_at).toLocaleString(t.dateLocale) }}</small></div>
            <div v-if="item.status === 'pending'" class="request-actions">
              <button type="button" class="reject" @click="$emit('review', item.user_id, 'reject')">{{ t.demoReject }}</button>
              <button type="button" class="approve" @click="$emit('review', item.user_id, 'approve')">{{ t.demoApprove }}</button>
            </div>
          </article>
        </div>
        <div v-else class="content-empty"><strong>{{ t.demoNoRequests }}</strong><p>{{ t.demoNoRequestsText }}</p></div>
      </section>
    </template>
  </section>
</template>
