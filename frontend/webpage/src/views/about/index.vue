<template>
  <div class="about-page">
    <Header />

    <main class="content about-page">
      <!-- 公司简介 -->
      <section class="about-intro">
        <h2>{{ $t('about.company.title') }}</h2>
        <p>{{ $t('about.company.text') }}</p>
      </section>

      <!-- 团队 -->
      <section class="team-section">
        <h2 class="team-title">{{ $t('team.title') }}</h2>

        <div class="team">
          <TeamMember
            v-for="member in team"
            :key="member.id"
            :member="member"
          />
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import TeamMember from '@/components/TeamMember.vue'

const team = [
  { id: 'chris', img: 'Chris.jpg' },
  { id: 'randall', img: 'Randall.jpg' },
  { id: 'penny', img: 'Penny.jpg' },
  { id: 'kiki', img: 'Kiki.jpg' },
  { id: 'tina', img: 'Tina.jpg' }
]
</script>

<style scoped>
.about-page {
  min-height: 100vh;
}
</style>