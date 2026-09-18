<script setup lang="ts">
defineProps<{ stacked?: boolean }>();
</script>

<template>
  <div class="realm-folio" :class="{'folio-stacks':stacked}">
    <div class="folio-underleaf" aria-hidden="true"></div>
    <div class="folio-materials" aria-hidden="true"><i class="folio-paper folio-left"></i><i class="folio-paper folio-right"></i></div>
    <div class="folio-spine" aria-hidden="true"><i></i></div>
    <div class="folio-bookmark" aria-hidden="true"></div>
    <slot/>
  </div>
</template>

<style scoped>
.realm-folio{position:relative;min-width:0;min-height:0;isolation:isolate;backdrop-filter:blur(20px) saturate(.74);border-radius:5px;box-shadow:0 22px 30px #132d3e40}
.folio-materials{position:absolute;inset:0;display:grid;grid-template-columns:1fr 1fr;z-index:-1;pointer-events:none}
.folio-paper{border:1px solid #c3e3e17d;box-shadow:inset 0 0 30px #9ecbda08}
.folio-left{border-radius:5px 14px 2px 5px;border-right-color:#d4e9ea21;background:linear-gradient(100deg,#183747ac,#163348c9)}
.folio-right{border-radius:14px 5px 5px 2px;border-left-color:#d4e9ea21;background:linear-gradient(90deg,#163348d4,#213747b8)}
.folio-spine{position:absolute;z-index:4;top:3px;bottom:-7px;left:calc(50% - 9px);width:18px;background:linear-gradient(90deg,transparent,#071e3547 44%,#bde3e767 49%,#d9bfdfab 50%,#071e3565 60%,transparent);border-radius:50%;pointer-events:none}
.folio-spine i{display:block;margin:auto;width:1px;height:100%;box-shadow:0 0 15px #c9b6e373}
.folio-underleaf{position:absolute;inset:10px 3px -7px;border:1px solid #c1dfe56e;border-bottom:3px double #b3d8e68a;background:#1536494d;border-radius:4px;z-index:-2;pointer-events:none;transform:rotate(.15deg)}
.folio-bookmark{position:absolute;z-index:5;top:-6px;left:calc(50% + 13px);width:12px;height:56px;background:linear-gradient(#ccb3da92,#9cafcf2e);clip-path:polygon(0 0,100% 0,100% 100%,50% 88%,0 100%);border-top:1px solid #e5cceb;pointer-events:none}
@media(max-width:700px){.folio-spine{width:12px;left:calc(50% - 6px)}.folio-bookmark{left:calc(50% + 8px);width:8px;height:40px}}
@media(max-width:900px){.folio-stacks .folio-materials{grid-template-columns:1fr}.folio-stacks .folio-right,.folio-stacks .folio-spine{display:none}.folio-stacks .folio-left{border-radius:5px 12px 5px 5px}.folio-stacks .folio-bookmark{left:auto;right:20px}}
</style>
