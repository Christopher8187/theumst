<script setup>
defineProps({ tr: { type: Function, required: true } });
defineEmits(["navigate"]);
</script>

<template>
  <footer class="site-footer">
    <div class="site-container">
      <strong>theumst</strong>
      <span>{{ tr("footer.line") }}</span>
      <span class="footer-legal">
        <a href="/privacy" @click.prevent="$emit('navigate', '/privacy')">{{ tr("footer.privacy") }}</a>
        <span aria-hidden="true">·</span>
        <span>© {{ new Date().getFullYear() }}</span>
      </span>
    </div>
  </footer>
</template>
