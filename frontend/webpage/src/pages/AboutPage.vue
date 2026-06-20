<script setup>
import { assetUrl } from "../../../urls.js";
import SiteHeader from "../components/SiteHeader.vue";

defineProps({ tr: Function, session: Object, titleKey: String, loginError: Boolean });
defineEmits(["navigate", "set-language"]);

const team = [
  { id: "chris", image: "Chris.jpg" },
  { id: "randall", image: "Randall.jpg" },
  { id: "penny", image: "Penny.jpg" },
  { id: "kiki", image: "Kiki.jpg" },
  { id: "tina", image: "Tina.jpg" }
];
</script>

<template>
  <SiteHeader
    :tr="tr"
    title-key="about.title"
    :session="session"
    @navigate="$emit('navigate', $event)"
    @set-language="$emit('set-language', $event)"
  />

  <main class="content about-page">
    <section class="about-intro">
      <h2>{{ tr("about.company.title") }}</h2>
      <p>{{ tr("about.company.text") }}</p>
    </section>

    <section class="team-section">
      <h2 class="team-title">{{ tr("team.title") }}</h2>

      <div class="team">
        <article v-for="member in team" :key="member.id" class="member">
          <img :src="assetUrl(member.image)" :alt="tr(`team.${member.id}.name`)">
          <h3>{{ tr(`team.${member.id}.name`) }}</h3>
          <p class="member-role">{{ tr(`team.${member.id}.role`) }}</p>

          <div class="member-field">
            <h4>{{ tr("team.field.bio") }}</h4>
            <p>{{ tr(`team.${member.id}.bio`) }}</p>
          </div>

          <div class="member-field">
            <h4>{{ tr("team.field.focus") }}</h4>
            <p>{{ tr(`team.${member.id}.focus`) }}</p>
          </div>
        </article>
      </div>
    </section>
  </main>
</template>
