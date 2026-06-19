<template>
  <article class="member">
    <img :src="image" :alt="memberName" />

    <h3>{{ memberName }}</h3>
    <p class="member-role">{{ role }}</p>

    <div class="member-field">
      <h4>{{ $t('team.field.bio') }}</h4>
      <p>{{ bio }}</p>
    </div>

    <div class="member-field">
      <h4>{{ $t('team.field.focus') }}</h4>
      <p>{{ focus }}</p>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  member: {
    type: Object,
    required: true
  }
})

const { tm } = useI18n()

const id = props.member.id

const image = `/images/${props.member.img}`
const memberName = computed(() => tm(`team.${id}.name`))
const role = computed(() => tm(`team.${id}.role`))
const bio = computed(() => tm(`team.${id}.bio`))
const focus = computed(() => tm(`team.${id}.focus`))
</script>

<style scoped>
.member {
  text-align: center;
}
.member img {
  width: 120px;
  border-radius: 50%;
}
.member-field {
  margin-top: 12px;
}
</style>