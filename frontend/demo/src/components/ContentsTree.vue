<script setup>
import { computed, nextTick, ref, watch } from "vue";
import {
  contentsItemKey,
  defaultExpandedContents,
  findSectionPath,
  flattenVisibleContents
} from "../domain/contents";

defineOptions({ name: "ContentsTree" });
const props = defineProps({
  items: { type: Array, default: () => [] },
  currentSectionId: { type: [Number, String], default: null },
  pageSize: { type: Number, default: 48 }
});
const emit = defineEmits(["select"]);

const expanded = ref(new Set());
const pageStart = ref(0);
const focusedKey = ref("");
const itemElements = new Map();
const safePageSize = computed(() => Math.max(12, Math.min(80, Number(props.pageSize) || 48)));
const allRows = computed(() => flattenVisibleContents(props.items, expanded.value));
const maxPageStart = computed(() => Math.max(0, allRows.value.length - safePageSize.value));
const pageEnd = computed(() => Math.min(allRows.value.length, pageStart.value + safePageSize.value));
const visibleRows = computed(() => allRows.value.slice(pageStart.value, pageEnd.value));

function isExpanded(row) {
  return expanded.value.has(row.key);
}

function sectionLabel(item) {
  return String(item.section_name || item.section_number || "Untitled section");
}

function revealCurrent(sectionId) {
  const path = findSectionPath(props.items, sectionId);
  if (!path.length) return;
  const next = new Set(expanded.value);
  for (const item of path.slice(0, -1)) next.add(contentsItemKey(item));
  expanded.value = next;
  const currentKey = contentsItemKey(path[path.length - 1]);
  focusedKey.value = currentKey;
  nextTick(() => {
    const index = allRows.value.findIndex(row => row.key === currentKey);
    if (index >= 0 && (index < pageStart.value || index >= pageEnd.value)) {
      pageStart.value = Math.min(maxPageStart.value, Math.max(0, index - Math.floor(safePageSize.value / 2)));
    }
  });
}

watch(() => props.items, items => {
  expanded.value = defaultExpandedContents(items, props.currentSectionId);
  pageStart.value = 0;
  focusedKey.value = contentsItemKey(findSectionPath(items, props.currentSectionId).at(-1) || items[0]);
}, { immediate: true });

watch(() => props.currentSectionId, revealCurrent, { immediate: true });

watch([allRows, safePageSize], () => {
  pageStart.value = Math.max(0, Math.min(pageStart.value, maxPageStart.value));
  if (!allRows.value.some(row => row.key === focusedKey.value)) {
    focusedKey.value = allRows.value[Math.min(pageStart.value, allRows.value.length - 1)]?.key || "";
  }
});

function setItemElement(key, element) {
  if (element) itemElements.set(key, element);
  else itemElements.delete(key);
}

function toggle(row) {
  if (!row.item.children?.length) return;
  const next = new Set(expanded.value);
  if (next.has(row.key)) next.delete(row.key);
  else next.add(row.key);
  expanded.value = next;
}

async function focusRow(index) {
  if (index < 0 || index >= allRows.value.length) return;
  const row = allRows.value[index];
  if (index < pageStart.value || index >= pageEnd.value) {
    pageStart.value = Math.min(maxPageStart.value, Math.max(0, index - Math.floor(safePageSize.value / 2)));
  }
  focusedKey.value = row.key;
  await nextTick();
  itemElements.get(row.key)?.focus();
}

async function onKeydown(event, row) {
  const index = allRows.value.findIndex(candidate => candidate.key === row.key);
  if (index < 0) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    await focusRow(index + 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    await focusRow(index - 1);
  } else if (event.key === "ArrowRight" && row.item.children?.length) {
    event.preventDefault();
    if (!isExpanded(row)) {
      toggle(row);
      await nextTick();
    } else {
      await focusRow(index + 1);
    }
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    if (isExpanded(row)) toggle(row);
    else if (row.parentKey) await focusRow(allRows.value.findIndex(candidate => candidate.key === row.parentKey));
  } else if (event.key === "Home") {
    event.preventDefault();
    await focusRow(0);
  } else if (event.key === "End") {
    event.preventDefault();
    await focusRow(allRows.value.length - 1);
  } else if (event.key === " ") {
    event.preventDefault();
    if (row.item.children?.length) toggle(row);
    else if (row.item.section_id != null) emit("select", row.item.section_id);
  }
}

async function movePage(direction) {
  const nextStart = Math.max(0, Math.min(maxPageStart.value, pageStart.value + direction * safePageSize.value));
  pageStart.value = nextStart;
  await nextTick();
  await focusRow(direction < 0 ? pageEnd.value - 1 : pageStart.value);
}
</script>

<template>
  <div class="contents-browser">
    <p v-if="!allRows.length" class="contents-empty">No sections are available for this book.</p>
    <template v-else>
      <div class="contents-window-summary" role="status">
        <span>Sections {{ pageStart + 1 }}–{{ pageEnd }} of {{ allRows.length }} currently visible</span>
        <span v-if="allRows.length > safePageSize">Only this bounded window is rendered.</span>
      </div>
      <button
        v-if="pageStart > 0"
        type="button"
        class="contents-page-button"
        @click="movePage(-1)"
      >
        ↑ Show earlier visible sections
      </button>
      <ol class="contents-tree contents-level-1" role="tree" aria-label="Book contents">
        <li v-for="row in visibleRows" :key="row.key" role="none" data-contents-row>
          <div
            class="contents-row"
            :class="{ current: Number(row.item.section_id) === Number(currentSectionId) }"
            :style="{ '--contents-depth': row.depth - 1 }"
          >
            <button
              v-if="row.item.children?.length"
              type="button"
              class="contents-toggle"
              tabindex="-1"
              :aria-label="`${isExpanded(row) ? 'Collapse' : 'Expand'} ${sectionLabel(row.item)}`"
              @click="toggle(row)"
            >
              <span aria-hidden="true">{{ isExpanded(row) ? '−' : '+' }}</span>
            </button>
            <span v-else class="contents-leaf" aria-hidden="true">·</span>
            <span class="contents-number">{{ row.item.section_number || '—' }}</span>
            <button
              :ref="element => setItemElement(row.key, element)"
              type="button"
              class="contents-entry contents-name"
              role="treeitem"
              :tabindex="focusedKey === row.key ? 0 : -1"
              :aria-level="row.depth"
              :aria-expanded="row.item.children?.length ? isExpanded(row) : undefined"
              :aria-current="Number(row.item.section_id) === Number(currentSectionId) ? 'location' : undefined"
              @focus="focusedKey = row.key"
              @keydown="onKeydown($event, row)"
              @click="row.item.section_id != null && emit('select', row.item.section_id)"
            >
              {{ sectionLabel(row.item) }}
            </button>
          </div>
        </li>
      </ol>
      <button
        v-if="pageEnd < allRows.length"
        type="button"
        class="contents-page-button"
        @click="movePage(1)"
      >
        Show later visible sections ↓
      </button>
    </template>
  </div>
</template>

<style scoped>
.contents-window-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 10px 0 6px;
  color: #8da0b2;
  font-size: 0.75rem;
}

.contents-row {
  padding-left: calc(var(--contents-depth) * 16px + 4px);
}

.contents-entry {
  min-width: 0;
  border: 0;
  padding: 10px 8px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.contents-entry:hover {
  color: #fffdf8;
}

.contents-entry:focus-visible,
.contents-toggle:focus-visible,
.contents-page-button:focus-visible {
  outline: 3px solid rgba(111, 216, 207, 0.72);
  outline-offset: 2px;
}

.contents-page-button {
  width: 100%;
  border: 1px solid rgba(111, 216, 207, 0.22);
  border-radius: 10px;
  padding: 9px 12px;
  background: rgba(111, 216, 207, 0.055);
  color: #b8cbc9;
  cursor: pointer;
}

.contents-empty {
  color: #8da0b2;
}

@media (max-width: 480px) {
  .contents-window-summary {
    display: block;
  }

  .contents-window-summary span {
    display: block;
  }
}

@media (prefers-reduced-motion: reduce) {
  .contents-entry,
  .contents-page-button,
  .contents-toggle {
    transition: none !important;
  }
}
</style>
