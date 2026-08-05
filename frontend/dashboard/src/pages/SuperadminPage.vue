<script setup>
defineProps({
  t: { type: Object, required: true },
  superMessage: String,
  superError: Boolean,
  sqlResult: String,
  sqlError: Boolean
});
const superUser = defineModel("superUser");
const superSql = defineModel("superSql");
defineEmits(["make-admin", "run-sql"]);
</script>

<template>
  <section class="dashboard-card wide-card">
    <p class="eyebrow">{{ t.superadmin }}</p>
    <h1>{{ t.superadminTitle }}</h1>
    <p class="muted">{{ t.superadminText }}</p>

    <form class="dashboard-form small-form" @submit.prevent="$emit('make-admin')" novalidate>
      <label>{{ t.userToPromote }}<input v-model="superUser" autocomplete="off"></label>
      <button type="submit">{{ t.giveAdmin }}</button>
    </form>
    <p v-if="superMessage" class="message key-output" :class="{ error: superError }">{{ superMessage }}</p>

    <section class="admin-panel danger-panel">
      <p class="eyebrow">{{ t.superSql }}</p>
      <h2>{{ t.superSqlTitle }}</h2>
      <p class="muted">{{ t.superSqlText }}</p>
      <form class="dashboard-form" @submit.prevent="$emit('run-sql')">
        <label>{{ t.sqlCode }}<textarea v-model="superSql" class="sql-box" rows="12"></textarea></label>
        <button type="submit">{{ t.runSql }}</button>
      </form>
      <pre v-if="sqlResult" class="result-box" :class="{ error: sqlError }">{{ sqlResult }}</pre>
    </section>
  </section>
</template>
