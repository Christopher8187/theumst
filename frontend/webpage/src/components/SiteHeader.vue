<script setup>
import { ref } from "vue";
import { assetUrl, dashboardUrl } from "../../../urls.js";
import { languageOptions } from "../utils/language";

defineProps({
  tr: { type: Function, required: true },
  titleKey: { type: String, default: "" },
  compact: Boolean,
  showUserCard: Boolean,
  session: { type: Object, default: null }
});

const emit = defineEmits(["navigate", "set-language"]);
const open = ref(false);

const nav = [
  ["/", "nav.home"],
  ["/news", "nav.news"],
  ["/about", "nav.about"],
  ["/wiki", "nav.wiki"],
  ["/login", "nav.login", "login"],
  ["/get", "nav.get", "get"]
];

function go(event, path) {
  event.preventDefault();
  emit("navigate", path);
}

function chooseLanguage(code) {
  emit("set-language", code);
  open.value = false;
}
</script>

<template>
  <header class="top" :class="{ 'login-top': compact }">
    <div class="brand">
      <a href="/" @click="go($event, '/')">
        <img class="logo" :src="assetUrl('logo.png')" :alt="tr('alt.logo')">
      </a>
      <h1>{{ tr("brand.title") }}</h1>
    </div>

    <nav class="nav">
      <template v-for="item in nav" :key="item[0]">
        <a
          v-if="!(item[2] === 'login' && session?.user)"
          :href="item[0]"
          :class="{ get: item[2] === 'get' }"
          @click="go($event, item[0])"
        >{{ tr(item[1]) }}</a>
      </template>

      <div class="language-menu">
        <button class="language-button" type="button" @click="open = !open">
          <img :src="assetUrl('translate.svg')" alt="">
          <span>{{ tr("language.label") }}</span>
        </button>

        <div class="language-dropdown" :class="{ open }">
          <button
            v-for="option in languageOptions"
            :key="option.code"
            type="button"
            @click="chooseLanguage(option.code)"
          >{{ tr(option.labelKey) }}</button>
        </div>
      </div>
    </nav>

    <section v-if="showUserCard && session?.user" class="home-user-card">
      <img :src="assetUrl('Chris.jpg')" alt="Profile picture">
      <div class="home-user-name">{{ session.user.username }}</div>
      <div class="home-user-alias">{{ session.user.alias || session.user.username }}</div>
      <p>{{ session.user.description || tr("home.noDescription") }}</p>
      <a :href="dashboardUrl('/dashboard/profile/')">{{ tr("dashboard.title") }}</a>
    </section>

    <h2 v-if="titleKey" class="hero-title">{{ tr(titleKey) }}</h2>
  </header>
</template>
