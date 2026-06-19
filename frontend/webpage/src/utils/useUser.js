import { ref } from 'vue'

export function useUser() {
  const user = ref(JSON.parse(localStorage.getItem('user')))

  return { user }
}
