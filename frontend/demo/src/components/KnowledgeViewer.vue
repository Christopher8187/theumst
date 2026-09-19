<script setup>
import { computed } from "vue";
import { renderMath } from "../math";
import NotebookMath from "./NotebookMath.vue";
import NotebookImageLinks from "./NotebookImageLinks.vue";

const props = defineProps({ t: Object, node: Object, notebook: Boolean, mode: { type: String, default: "text" } });
const emit = defineEmits(["soon", "open-image"]);
const statement = computed(() => renderMath(props.node?.statement || ""));
const working = computed(() => renderMath(props.node?.working || ""));
const hasWorking = computed(() => !!props.node?.working?.trim());

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
      <span class="type-chip" :class="node.type">{{ t['type_'+node.type] || node.type }}</span>
      <span>#{{ node.book_order_rank ?? node.source_order?.[0] ?? node.knowledge_id }}</span>
      <span v-html="renderMath(node.label || '')"></span>
      <strong :title="mode === 'questions' ? t.questionSymbol : t.bookSymbol">{{ mode === 'questions' ? '?' : '▥' }}</strong>
    </div>
    <section class="knowledge-section statement-section">
      <div class="knowledge-section-head"><h2>{{ t.statement }}</h2><button type="button" @click="$emit('soon', 'sound')">▶ {{ t.listen }}</button></div>
      <div v-if="notebook" class="math-content" @click="openInlineImage"><NotebookMath :content="node.statement"><template v-if="!hasWorking && node.images?.length" #default><NotebookImageLinks :images="node.images" :label="t.bookImage" @open-image="$emit('open-image', $event)"/></template></NotebookMath></div>
      <div v-else class="math-content" v-html="statement" @click="openInlineImage"></div>
    </section>
    <section class="knowledge-section workings-section">
      <div v-if="!notebook || hasWorking" class="knowledge-section-head"><h2>{{ t.workings }}</h2><button type="button" @click="$emit('soon', notebook?'sound':'prompt')">{{notebook?'▶':'✦'}} {{ notebook?t.listen:t.prompt }}</button></div>
      <div v-if="notebook && hasWorking" class="math-content" @click="openInlineImage"><NotebookMath :content="node.working"><template v-if="node.images?.length" #default><NotebookImageLinks :images="node.images" :label="t.bookImage" @open-image="$emit('open-image', $event)"/></template></NotebookMath></div>
      <div v-else-if="!notebook" class="math-content" v-html="working" @click="openInlineImage"></div>
      <div v-if="!notebook && node.images?.length" class="knowledge-images">
        <button v-for="image in node.images" :key="image.source_image_id" type="button" @click="$emit('open-image', image)">
          ▧ {{ image.semantic_context_name || `${t.bookImage} ${image.source_image_id}` }}
        </button>
      </div>
      <button v-if="!notebook" class="sound-corner" type="button" :aria-label="t.listen" @click="$emit('soon', 'sound')">▶</button>
    </section>
  </article>
  <div v-else class="knowledge-empty">{{ t.selectNode }}</div>
</template>
