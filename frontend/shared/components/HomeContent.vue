<script setup lang="ts">
import { computed } from "vue";
const props = defineProps<{
  language: string;
  labels: Record<string, string>;
}>();
defineEmits<{ demo: []; about: [] }>();
const copy = computed(
  () =>
    ({
      zh: [
        "再向前一步，",
        "理解更多。",
        "打开一本魔典，追随一个想法。在一个留有思考空间的世界里，以自己的节奏建立联系。",
        "页边笔记",
        "一个熟悉的想法。",
        "一种新的观察方式。",
      ],
      ja: [
        "理解へ、",
        "もう少し先へ。",
        "グリモアを開き、ひとつの考えをたどる。考える余地のある世界で、自分のペースでつながりを見つけよう。",
        "余白のメモ",
        "馴染みのある考え。",
        "新しい見方。",
      ],
    })[props.language] || [
      "A little further",
      "into understanding.",
      "Open a grimoire. Follow an idea. Make connections at your own pace, in a world that leaves room to think.",
      "NOTES FROM THE MARGIN",
      "One familiar idea.",
      "A new way to see it.",
    ],
);
</script>
<template>
  <div class="home-layout">
    <div>
      <div class="kicker">THEUMST</div>
      <h1>{{ copy[0] }}<br />{{ copy[1] }}</h1>
      <p class="lede">{{ copy[2] }}</p>
      <div class="button-row">
        <button class="primary" @click="$emit('demo')">
          {{ labels.demo }} ↗</button
        ><button @click="$emit('about')">{{ labels.about }} Theumst</button>
      </div>
    </div>
    <aside class="field-note">
      <span>{{ copy[3] }}</span
      ><svg viewBox="0 0 150 135" aria-hidden="true">
        <circle cx="76" cy="66" r="41" />
        <ellipse
          cx="76"
          cy="66"
          rx="59"
          ry="20"
          transform="rotate(-29 76 66)"
        />
        <path
          d="M76 6v120M16 66h122M36 30l80 76M32 95l89-53"
          stroke-dasharray="2 4"
        />
        <circle class="glint" cx="116" cy="49" r="3" />
        <circle class="glint" cx="38" cy="85" r="2" />
        <path d="M62 66h28M76 52v28" /></svg
      ><span class="formula">∇ · E = ρ / ε₀</span>
      <p>{{ copy[4] }}<br />{{ copy[5] }}</p>
    </aside>
  </div>
</template>
