import { createRouter, createWebHashHistory } from 'vue-router'
import News from '@/views/news/index.vue'
import Login from '@/views/login/index.vue'

const routes = [
  { path: '/', redirect: '/news' },
  { path: '/news', component: News },
  { path: '/login', component: Login },
  {
  path: '/about',
  component: () => import('@/views/about/index.vue')
}
]

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/wiki',
      component: () => import('@/pages/WikiPage.vue')
    }
  ]
})

