<script setup>
import { computed } from "vue";
import ContentsTree from "./ContentsTree.vue";
import { buildContentsTree } from "../domain/contents";
import BookObject from "./BookObject.vue";

const props = defineProps({
  t: Object,
  book: Object,
  contents: Array,
  summoning: Boolean,
});
defineEmits(["summon"]);
const tree = computed(() =>
  buildContentsTree(props.contents).flatMap((section) =>
    section.children.length &&
    (section.is_book_root === true ||
      ["", "0"].includes(String(section.section_number ?? "")))
      ? section.children
      : [section],
  ),
);
</script>

<template>
  <section v-if="book" class="book-detail view-pad">
    <header class="view-heading">
      <div>
        <p class="demo-kicker">{{ t.title }}</p>
        <h1>{{ book.title }}</h1>
      </div>
      <span class="edition-chip">{{ book.version }}</span>
    </header>

    <div class="book-detail-grid">
      <div class="book-pedestal">
        <BookObject :title="book.title" large />
        <p>
          <span>{{ t.isbn }}:</span> {{ book.isbn || "—" }}
        </p>
      </div>
      <div class="summary-oracle">
        <div class="oracle-head">
          <span class="oracle-sigil">✦</span>
          <div>
            <p class="demo-kicker">THEUMST</p>
            <h2>{{ t.summary }}</h2>
          </div>
        </div>
        <p class="summary-copy">{{ book.summary || book.title }}</p>
        <h3>{{ t.contents }}</h3>
        <ContentsTree :t="t" :items="tree" />
        <button
          class="primary-button summon-button"
          :class="{ summoning }"
          type="button"
          @click="$emit('summon')"
        >
          <span>✧</span>{{ book.summoned ? t.summoned : t.summon }}
        </button>
      </div>
    </div>
  </section>
</template>
