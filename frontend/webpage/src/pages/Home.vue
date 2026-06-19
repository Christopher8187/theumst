<template>
  <HeaderNav />

  <main class="content">
    <FeatureSection
      image="/images/cave.jpg"
      altKey="alt.cave"
      titleKey="home.explore.title"
      textKey="home.explore.text"
    />

    <FeatureSection
      image="/images/graph.jpg"
      altKey="alt.graph"
      titleKey="home.learn.title"
      textKey="home.learn.text"
      reverse
    />
  </main>
</template>

<script setup>
import HeaderNav from '@/components/HeaderNav.vue'
import FeatureSection from '@/components/FeatureSection.vue'
</script>