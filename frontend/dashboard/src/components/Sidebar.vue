<script setup>
defineProps({
  t: { type: Object, required: true },
  route: { type: String, required: true },
  accessPoints: { type: Array, required: true },
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
    <button v-if="accessPoints.includes('profile')" class="side-link" :class="{ active: route === 'profile' }" @click="$emit('go', 'profile')">{{ t.profile }}</button>
    <button v-if="accessPoints.includes('api-keys')" class="side-link" :class="{ active: route === 'api-keys' }" @click="$emit('go', 'api-keys')">{{ t.apiKeys }}</button>
    <button v-if="accessPoints.includes('profile')" class="side-link demo-side-link" :class="{ active: route === 'demo' }" @click="$emit('go', 'demo')"><span class="side-icon">✦</span>{{ t.demo }}</button>
    <button v-if="accessPoints.includes('books')" class="side-link" :class="{ active: route === 'books' }" @click="$emit('go', 'books')"><span class="side-icon">▤</span>{{ t.books }}</button>
    <button v-if="accessPoints.includes('admin')" class="side-link" :class="{ active: route === 'users' }" @click="$emit('go', 'users')"><span class="side-icon">◎</span>{{ t.users }}</button>
    <button v-if="accessPoints.includes('media')" class="side-link" :class="{ active: route === 'media' }" @click="$emit('go', 'media')"><span class="side-icon">◉</span>{{ t.media }}</button>
    <button v-if="accessPoints.includes('admin')" class="side-link" :class="{ active: route === 'admin' }" @click="$emit('go', 'admin')">{{ t.admin }}</button>
    <button v-if="accessPoints.includes('superadmin')" class="side-link" :class="{ active: route === 'superadmin' }" @click="$emit('go', 'superadmin')">{{ t.superadmin }}</button>

    <button class="language-trigger" @click="$emit('choose-language')">
      <img :src="translateSrc" alt="">
      <span>{{ t.language }}</span>
    </button>

    <button class="side-link signout" @click="$emit('sign-out')">{{ t.signOut }}</button>
  </aside>
</template>
