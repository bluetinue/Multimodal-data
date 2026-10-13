import { createRouter, createWebHistory } from 'vue-router'
import { checkSession } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/StudioLayout.vue'),
      children: [
        { path: '', redirect: '/t2i' },
        { path: 't2i', name: 't2i', component: () => import('@/views/T2iView.vue') },
        { path: 'i2v', name: 'i2v', component: () => import('@/views/I2vView.vue') },
        { path: 'library', name: 'library', component: () => import('@/views/LibraryView.vue') },
        { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) {
    return true
  }
  try {
    const ok = await checkSession()
    if (!ok) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  } catch {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
