<script setup>
defineProps({
  t: { type: Object, required: true },
  route: { type: String, required: true },
  isAdmin: Boolean,
  isSuperadmin: Boolean,
  logoSrc: { type: String, required: true },
  translateSrc: { type: String, required: true },
  homeUrl: { type: String, required: true }
});

defineEmits(["go", "choose-language", "sign-out"]);
</script>

<template>
  <aside class="sidebar">
    <a :href="homeUrl"><img class="dash-logo" :src="logoSrc" alt="UMST"></a>

    <a class="side-link" :href="homeUrl">{{ t.home }}</a>
    <button class="side-link" :class="{ active: route === 'profile' }" @click="$emit('go', 'profile')">{{ t.profile }}</button>
    <button class="side-link" :class="{ active: route === 'api-keys' }" @click="$emit('go', 'api-keys')">{{ t.apiKeys }}</button>
    <button v-if="isAdmin" class="side-link" :class="{ active: route === 'admin' }" @click="$emit('go', 'admin')">{{ t.admin }}</button>
    <button v-if="isSuperadmin" class="side-link" :class="{ active: route === 'superadmin' }" @click="$emit('go', 'superadmin')">{{ t.superadmin }}</button>

    <button class="language-trigger" @click="$emit('choose-language')">
      <img :src="translateSrc" alt="">
      <span>{{ t.language }}</span>
    </button>

    <button class="side-link signout" @click="$emit('sign-out')">{{ t.signOut }}</button>
  </aside>
</template>
