<template>
  <div class="wiki-page">
    <AppHeader />

    <main class="content empty">
      <!-- 预留 Wiki 内容 -->
      <section class="wiki-content">
        <h2>{{ t('wiki.title') }}</h2>
        <p>{{ t('wiki.intro') }}</p>

        <!-- 示例内容 -->
        <article>
          <h3>{{ t('wiki.section1.title') }}</h3>
          <p>{{ t('wiki.section1.desc') }}</p>
        </article>

        <article>
          <h3>{{ t('wiki.section2.title') }}</h3>
          <p>{{ t('wiki.section2.desc') }}</p>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import AppHeader from '@/components/AppHeader.vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
</script>