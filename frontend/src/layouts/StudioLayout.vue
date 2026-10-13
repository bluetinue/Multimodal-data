<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AppstoreOutlined,
  LogoutOutlined,
  PictureOutlined,
  SettingOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { fetchSettings, logout } from '@/api/client'
import type { Settings } from '@/types'

const route = useRoute()
const router = useRouter()
const settings = ref<Settings | null>(null)
const selected = computed(() => [route.path])

const menuItems = [
  { key: '/t2i', icon: PictureOutlined, label: '文生图批次' },
  { key: '/i2v', icon: VideoCameraOutlined, label: '图生视频批次' },
  { key: '/library', icon: AppstoreOutlined, label: '样本库' },
  { key: '/settings', icon: SettingOutlined, label: '设置' },
]

const items = menuItems.map((item) => ({
  key: item.key,
  icon: () => h(item.icon),
  label: item.label,
}))

let timer: number | undefined

async function refresh() {
  try {
    settings.value = await fetchSettings()
  } catch {
    settings.value = null
  }
}

async function onLogout() {
  await logout()
  message.success('已退出')
  router.push({ name: 'login' })
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, 8000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <a-layout class="shell">
    <a-layout-sider width="248" theme="dark" class="sider">
      <div class="brand">
        <div class="mark">MD</div>
        <div>
          <div class="display title">数据中台</div>
          <div class="sub">文生图 · 图生视频</div>
        </div>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="selected"
        :items="items"
        @click="({ key }) => router.push(String(key))"
      />
      <div class="foot">
        <div>
          <span class="status-pill" :class="settings ? 'ok' : 'bad'">服务</span>
        </div>
        <div style="margin-top: 8px">
          <span class="status-pill" :class="settings?.comfy?.ok ? 'ok' : 'bad'">ComfyUI</span>
        </div>
        <a-button block class="logout" @click="onLogout">
          <LogoutOutlined />
          退出
        </a-button>
      </div>
    </a-layout-sider>
    <a-layout-content class="content">
      <router-view />
    </a-layout-content>
  </a-layout>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  background: transparent;
}
.sider {
  background: rgba(10, 16, 22, 0.92) !important;
  border-right: 1px solid var(--line);
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 24px 18px 18px;
}
.mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-family: 'Sora', sans-serif;
  font-weight: 700;
  color: #041014;
  background: linear-gradient(135deg, #2dd4bf, #f5a524);
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.sub {
  color: var(--muted);
  font-size: 12px;
}
.foot {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 18px;
}
.logout {
  margin-top: 14px;
}
.content {
  padding: 28px 32px 48px;
  max-width: 1180px;
}
</style>
