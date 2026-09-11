<script setup lang="ts">
import { computed, ref } from "vue";
import logo from "../assets/logo-clear.svg";
const props = defineProps<{
  signedIn: boolean;
  labels: Record<string, string>;
  openPages: string[];
}>();
const emit = defineEmits<{ open: [id: string]; toggle: [id: string] }>();
const dock = ref<HTMLElement>();
const pages = computed(() => [
  "home",
  "about",
  "news",
  "wiki",
  "demo",
  ...(!props.signedIn ? ["login"] : []),
  "get",
  "settings",
]);
const paths: Record<string, string> = {
  home: "M3 11 12 3l9 8M5 10v11h5v-7h4v7h5V10",
  about: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 11v6M12 7v1",
  news: "M4 4h14v17H4zM18 8h3v13h-3M7 7h8M7 11h8M7 15h3M12 15h3M7 18h3M12 18h3",
  wiki: "M12 5C8 2 4 3 2 4v15c4-2 7-1 10 1 3-2 6-3 10-1V4c-4-2-7-1-10 1v15M5 8h4M15 8h4M5 11h4M15 11h4",
  demo: "M6 3h12l3 18H3zM6 8h12M9 13l6 4-6 2z",
  login: "M13 3h7v18h-7M3 12h12M10 7l5 5-5 5",
  get: "M12 3v18M3 12h18M5 5l14 14M19 5 5 19",
  settings:
    "M9 3h6l1 4 4 1v7l-4 1-1 5H9l-1-5-4-1V8l4-1zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
};
</script>
<template>
  <header class="topbar">
    <button
      class="brand"
      :aria-label="'Theumst ' + labels.home"
      @click="emit('open', 'home')"
    >
      <img :src="logo" alt="UMST" /><span
        ><span class="wordmark">theumst</span
        ><small>A PLACE TO LEARN</small></span
      >
    </button>
    <div class="topright">
      <button
        class="account-button"
        @click="emit('open', signedIn ? 'profile' : 'login')"
      >
        <span v-if="signedIn" class="account-dot"></span
        >{{ labels[signedIn ? "yourProfile" : "login"]
        }}<span v-if="signedIn" aria-hidden="true">▾</span>
      </button>
    </div>
  </header>
  <nav class="dock" :aria-label="labels.pages">
    <button
      class="dock-arrow"
      :aria-label="labels.previous"
      @click="dock?.scrollBy({ left: -240, behavior: 'smooth' })"
    >
      ‹
    </button>
    <div ref="dock" class="dock-list">
      <button
        v-for="id in pages"
        :key="id"
        :data-page="id"
        class="dock-item"
        :class="{ open: openPages.includes(id) }"
        :aria-pressed="openPages.includes(id)"
        @click="emit('toggle', id)"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="paths[id]" /></svg
        ><span>{{ labels[id] }}</span>
      </button>
    </div>
    <button
      class="dock-arrow"
      :aria-label="labels.more"
      @click="dock?.scrollBy({ left: 240, behavior: 'smooth' })"
    >
      ›
    </button>
  </nav>
</template>
