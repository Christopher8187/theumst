<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { apiFetch } from "../../urls.js";
import { useI18n } from "../../dashboard/src/utils/i18n.js";
import { roleName } from "../desktopText.js";
import MemberCard from "./MemberCard.vue";
const props = defineProps<{
  user: any;
  labels: Record<string, string>;
  language: string;
  open: boolean;
  requestedTab?: string;
}>();
const emit = defineEmits<{
  updated: [user: any];
  dashboard: [];
  card: [];
  news: [];
  signout: [];
}>();
const { t, setLang } = useI18n();
watch(() => props.language, setLang, { immediate: true });
const tab = ref("details"),
  editing = ref(false),
  draft = ref({ ...props.user }),
  message = ref(""),
  error = ref(false),
  busy = ref(false);
const subscription = ref<any>(null),
  choice = ref(false),
  subscriptionLoading = ref(false),
  subscriptionError = ref("");
const newEmail = ref(""),
  password = ref("");
watch(
  () => props.user,
  (value) => {
    draft.value = { ...value };
  },
);
watch(
  () => props.open,
  (value) => {
    if (value) {
      tab.value = props.requestedTab || "details";
      message.value = "";
      if (tab.value === "subscriptions") loadSubscriptions();
    }
  },
);
watch(
  () => props.requestedTab,
  (value) => {
    if (value) {
      tab.value = value;
      if (value === "subscriptions") loadSubscriptions();
    }
  },
  { immediate: true },
);
const status = computed(() => props.labels[subscription.value?.status] || "");
async function loadSubscriptions() {
  subscriptionLoading.value = true;
  subscriptionError.value = "";
  try {
    const res = await apiFetch("/api/me/subscriptions");
    if (!res.ok) throw Error(props.labels.loadError);
    subscription.value = await res.json();
    choice.value = subscription.value.news;
  } catch (e: any) {
    subscriptionError.value = e.message;
  } finally {
    subscriptionLoading.value = false;
  }
}
function select(value: string, focus = false) {
  tab.value = value;
  message.value = "";
  if (value === "subscriptions") loadSubscriptions();
  if (focus) nextTick(() => document.getElementById("tab-" + value)?.focus());
}
function key(event: KeyboardEvent) {
  if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    select(
      event.key === "Home"
        ? "details"
        : event.key === "End"
          ? "subscriptions"
          : tab.value === "details"
            ? "subscriptions"
            : "details",
      true,
    );
  }
}
async function request(path: string, body: any) {
  busy.value = true;
  message.value = "";
  error.value = false;
  try {
    const res = await apiFetch(path, {
      method:
        path === "/api/me" || path.endsWith("subscriptions") ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw Error(data.detail || props.labels.accountError);
    return data;
  } catch (e: any) {
    error.value = true;
    message.value = e.message;
    return null;
  } finally {
    busy.value = false;
  }
}
async function save() {
  const data = await request("/api/me", {
    username: draft.value.username,
    email: props.user.email,
    alias: draft.value.alias,
    description: draft.value.description,
  });
  if (data) {
    emit("updated", { ...props.user, ...draft.value });
    message.value = t.value.saved;
    editing.value = false;
  }
}
async function saveSubscriptions() {
  const data = await request("/api/me/subscriptions", { news: choice.value });
  if (data) {
    subscription.value = data;
    choice.value = data.news;
    message.value = props.labels.saved;
  }
}
async function changeEmail() {
  const data = await request("/auth/email-change/request", {
    new_email: newEmail.value,
    current_password: password.value,
  });
  password.value = "";
  if (data) message.value = t.value.emailChangeSent;
}
</script>
<template>
  <nav class="profile-tabs" role="tablist" :aria-label="labels.profile">
    <button
      v-for="id in ['details', 'subscriptions']"
      :id="'tab-' + id"
      :key="id"
      role="tab"
      :aria-selected="tab === id"
      :tabindex="tab === id ? 0 : -1"
      aria-controls="profile-panel"
      @keydown="key"
      @click="select(id)"
    >
      {{ labels[id] }}
    </button>
  </nav>
  <div id="profile-panel" role="tabpanel" :aria-labelledby="'tab-' + tab">
    <template v-if="tab === 'details'"
      ><div class="profile-layout">
        <div>
          <h2>{{ labels.yourProfile }}</h2>
          <dl>
            <div>
              <dt>{{ t.username }}</dt>
              <dd>{{ user.username }}</dd>
            </div>
            <div>
              <dt>{{ t.accountType }}</dt>
              <dd>{{ roleName(user.authority_type) }}</dd>
            </div>
          </dl>
          <button class="quiet-link" @click="editing = !editing">
            {{ labels.edit }}</button
          ><button class="quiet-link signout" @click="emit('signout')">
            {{ t.signOut }}
          </button>
        </div>
        <div class="card-area">
          <MemberCard :user="user" />
          <div class="profile-actions">
            <button @click="emit('card')">{{ labels.viewCard }} ↗</button
            ><button class="primary" @click="emit('dashboard')">
              {{ labels.openDashboard }} ↗
            </button>
          </div>
        </div>
      </div>
      <div v-if="editing" class="profile-edit">
        <form class="desktop-form" @submit.prevent="save">
          <label
            >{{ t.username }}<input v-model="draft.username" required /></label
          ><label
            >{{ t.email
            }}<input :value="user.email" type="email" readonly /></label
          ><label>{{ t.alias }}<input v-model="draft.alias" /></label
          ><label
            >{{ t.description
            }}<textarea v-model="draft.description" rows="3"></textarea></label
          ><button :disabled="busy">{{ t.saveProfile }}</button>
        </form>
        <h3>{{ t.changeEmail }}</h3>
        <p>{{ t.changeEmailText }}</p>
        <form class="desktop-form" @submit.prevent="changeEmail">
          <label
            >{{ t.newEmail
            }}<input
              v-model="newEmail"
              type="email"
              autocomplete="email"
              required /></label
          ><label
            >{{ t.currentPassword
            }}<input
              v-model="password"
              type="password"
              autocomplete="current-password"
              required /></label
          ><button :disabled="busy">{{ t.sendEmailChange }}</button>
        </form>
      </div></template
    >
    <div v-else class="subscriptions-content">
      <h2>{{ labels.newsTitle }}</h2>
      <p class="subscription-intro">{{ labels.newsIntro }}</p>
      <p class="subscription-address">{{ user.email }}</p>
      <p v-if="subscriptionLoading">{{ labels.loading }}</p>
      <div v-else-if="subscriptionError" role="alert">
        {{ subscriptionError }}
        <button @click="loadSubscriptions">{{ labels.retry }}</button>
      </div>
      <template v-else-if="subscription"
        ><div class="subscription-row">
          <label
            ><span
              ><strong>{{ labels.newsChoice }}</strong
              ><small>{{ labels.newsDescription }}</small></span
            ><input
              v-model="choice"
              type="checkbox"
              :disabled="busy || subscription.status === 'suppressed'"
          /></label>
        </div>
        <div class="subscription-bottom">
          <span class="subscription-status">{{ status }}</span
          ><button
            class="primary"
            :disabled="busy || subscription.status === 'suppressed'"
            @click="saveSubscriptions"
          >
            {{ labels.save }}
          </button>
        </div>
        <p
          v-if="subscription.status === 'pending_confirmation'"
          class="pending-email"
        >
          {{ labels.pending }}
        </p>
        <p v-if="subscription.status === 'suppressed'" class="pending-email">
          {{ labels.suppressedNote }}
        </p></template
      >
      <p class="subscription-footnote">{{ labels.footnote }}</p>
      <button class="quiet-link" @click="emit('news')">
        {{ labels.news }} ↗
      </button>
    </div>
  </div>
  <p
    v-if="message"
    class="profile-message"
    :class="{ error }"
    :role="error ? 'alert' : 'status'"
  >
    {{ message }}
  </p>
</template>
