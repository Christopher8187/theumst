<script setup lang="ts">
import { roleName } from "../desktopText.js";
defineProps<{ user: any; large?: boolean }>();
</script>
<template>
  <div class="role-card" :class="{ large }">
    <span class="card-top"><span>THEUMST</span><span>MEMBER</span></span
    ><span class="card-role">{{ roleName(user.authority_type) }}</span
    ><span class="card-name">{{ user.alias || user.username }}</span
    ><span class="card-star" aria-hidden="true">✧</span
    ><span class="card-bottom">AT HOME BETWEEN WORLDS</span>
  </div>
</template>
