<script setup>
import { ref } from "vue";

defineProps({
  t: { type: Object, required: true },
  apiUrl: { type: Function, required: true },
  niceSize: { type: Function, required: true },
  parentPath: String,
  storagePath: String,
  storageMode: String,
  storageItems: { type: Array, required: true },
  storageMessage: String,
  storageError: Boolean,
  adminResult: String,
  adminError: Boolean,
});

const fileInput = ref(null);

const adminSql = defineModel("adminSql");
const folderName = defineModel("folderName");
const storageName = defineModel("storageName");
const storageText = defineModel("storageText");

defineEmits(["run-sql", "load-storage", "open-storage", "create-folder", "new-file", "upload-file", "delete-storage", "save-storage"]);
</script>

<template>
  <section class="dashboard-card wide-card">
    <p class="eyebrow">{{ t.admin }}</p>
    <h1>{{ t.adminTitle }}</h1>
    <p class="muted">{{ t.adminText }}</p>

    <form class="dashboard-form" @submit.prevent="$emit('run-sql')">
      <label>{{ t.sqlCode }}<textarea v-model="adminSql" class="sql-box" rows="10"></textarea></label>
      <button type="submit">{{ t.runSql }}</button>
    </form>

    <pre v-if="adminResult" class="result-box" :class="{ error: adminError }">{{ adminResult }}</pre>

    <section class="storage-panel">
      <div class="storage-head">
        <div>
          <p class="eyebrow">{{ t.files }}</p>
          <h2>{{ t.objectStorage }}</h2>
          <p class="muted">{{ t.storageText }} <strong>{{ storageMode }}</strong></p>
        </div>
        <button type="button" @click="$emit('load-storage')">{{ t.refresh }}</button>
      </div>

      <div class="storage-tools">
        <button type="button" :disabled="!storagePath" @click="$emit('load-storage', parentPath)">← {{ t.up }}</button>
        <span class="path-pill">/{{ storagePath }}</span>
      </div>

      <div class="storage-actions">
        <form @submit.prevent="$emit('create-folder')">
          <input v-model="folderName" :placeholder="t.newFolder" autocomplete="off">
          <button type="submit">{{ t.createFolder }}</button>
        </form>
        <button type="button" @click="$emit('new-file')">{{ t.newFile }}</button>
        <button type="button" @click="fileInput?.click()">{{ t.upload }}</button>
        <input ref="fileInput" class="hidden-file" type="file" @change="$emit('upload-file', $event)">
      </div>

      <div class="storage-grid">
        <div class="file-list">
          <article v-for="item in storageItems" :key="item.key" class="file-row">
            <button class="file-name" type="button" @click="$emit('open-storage', item)">
              <span>{{ item.type === 'folder' ? '📁' : '📄' }}</span>
              <strong>{{ item.name }}</strong>
            </button>
            <span>{{ item.type }}</span>
            <span>{{ niceSize(item.size) }}</span>
            <div class="file-buttons">
              <a v-if="item.type === 'file'" :href="apiUrl(`/api/admin/storage/download?path=${encodeURIComponent(item.key)}`)">{{ t.download }}</a>
              <button type="button" @click="$emit('delete-storage', item)">{{ t.delete }}</button>
            </div>
          </article>
          <p v-if="!storageItems.length" class="empty-list">{{ t.emptyFolder }}</p>
        </div>

        <form class="storage-editor" @submit.prevent="$emit('save-storage')">
          <label>{{ t.filePath }}<input v-model="storageName" autocomplete="off" :placeholder="storagePath ? `${storagePath}/notes.txt` : 'notes.txt'"></label>
          <label>{{ t.fileContent }}<textarea v-model="storageText" rows="14"></textarea></label>
          <button type="submit">{{ t.saveFile }}</button>
          <p v-if="storageMessage" class="message key-output" :class="{ error: storageError }">{{ storageMessage }}</p>
        </form>
      </div>
    </section>
  </section>
</template>
