<script setup>
import { computed } from "vue";
import { renderMath } from "../math";

const props = defineProps({ t: Object, node: Object, mode: { type: String, default: "text" } });
const emit = defineEmits(["soon", "open-image"]);
const statement = computed(() => renderMath(props.node?.statement || ""));
const working = computed(() => renderMath(props.node?.working || ""));

function openInlineImage(event) {
  const trigger = event.target.closest?.("[data-image-id]");
  if (!trigger) return;
  const imageId = String(trigger.dataset.imageId || "");
  const image = (props.node?.images || []).find(item => String(item.source_image_id) === imageId);
  if (image) emit("open-image", image);
}
</script>

<template>
  <article v-if="node" class="knowledge-viewer">
    <div class="knowledge-meta">
      <span class="type-chip" :class="node.type">{{ node.type }}</span>
      <span>#{{ node.knowledge_id }}</span>
      <span v-html="renderMath(node.label || '')"></span>
      <strong :title="mode === 'questions' ? t.questionSymbol : t.bookSymbol">{{ mode === 'questions' ? '?' : '▥' }}</strong>
    </div>
    <section class="knowledge-section statement-section">
      <div class="knowledge-section-head"><h2>{{ t.statement }}</h2><button type="button" @click="$emit('soon', 'sound')">▶ {{ t.listen }}</button></div>
      <div class="math-content" v-html="statement" @click="openInlineImage"></div>
    </section>
    <section class="knowledge-section workings-section">
      <div class="knowledge-section-head"><h2>{{ t.workings }}</h2><button type="button" @click="$emit('soon', 'prompt')">✦ {{ t.prompt }}</button></div>
      <div class="math-content" v-html="working" @click="openInlineImage"></div>
      <div v-if="node.images?.length" class="knowledge-images">
        <button v-for="image in node.images" :key="image.source_image_id" type="button" @click="$emit('open-image', image)">
          ▧ {{ image.semantic_context_name || `${t.bookImage} ${image.source_image_id}` }}
        </button>
      </div>
      <button class="sound-corner" type="button" :aria-label="t.listen" @click="$emit('soon', 'sound')">▶</button>
    </section>
  </article>
  <div v-else class="knowledge-empty">{{ t.selectNode }}</div>
</template>
