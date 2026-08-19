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
  ["/about", "nav.about"],
  ["/news", "nav.news"],
  ["/wiki", "nav.wiki"],
  ["/demo", "nav.demo", "demo"],
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
  <header class="site-header" :class="{ 'compact-header': compact }">
    <div class="site-nav-shell">
      <a class="brand" href="/" @click="go($event, '/')">
        <img class="logo" :src="assetUrl('logo.png')" :alt="tr('alt.logo')">
        <span>{{ tr("brand.title") }}</span>
      </a>

      <nav class="nav">
      <template v-for="item in nav" :key="item[0]">
        <a
          v-if="!(item[2] === 'login' && session?.user)"
          :href="item[2] === 'demo' ? (session?.user ? dashboardUrl('/dashboard/demo/') : '/login?next=/dashboard/demo/') : item[0]"
          :class="{ get: item[2] === 'get' }"
          @click="item[2] === 'demo' ? null : go($event, item[0])"
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

      <a v-if="session?.user" class="account-link" :href="dashboardUrl('/dashboard/profile/')">
        <span class="account-dot"></span>{{ session.user.alias || session.user.username }}
      </a>
    </div>

    <section v-if="showUserCard && session?.user" class="home-user-card site-container">
      <span>{{ tr("home.welcomeBack") }}, <strong>{{ session.user.alias || session.user.username }}</strong></span>
      <a :href="dashboardUrl('/dashboard/profile/')">{{ tr("dashboard.title") }} →</a>
    </section>

    <div v-if="titleKey" class="page-heading site-container">
      <p class="section-kicker">{{ tr("brand.category") }}</p>
      <h1>{{ tr(titleKey) }}</h1>
    </div>
  </header>
</template>
