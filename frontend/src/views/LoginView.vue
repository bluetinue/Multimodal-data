<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { login } from '@/api/client'

const token = ref('')
const loading = ref(false)
const router = useRouter()
const route = useRoute()

async function submit() {
  loading.value = true
  try {
    await login(token.value)
    message.success('已进入工作台')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/t2i'
    router.replace(redirect)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="scanline" />
    <a-card class="panel-card box" :bordered="false">
      <div class="eyebrow">MULTIMODAL DATA STUDIO</div>
      <h1 class="display">数据中台</h1>
      <p>输入共享访问口令，进入文生图与图生视频造数工作台。</p>
      <a-form layout="vertical" @finish="submit">
        <a-form-item label="访问口令" name="token" :rules="[{ required: true, message: '请输入口令' }]">
          <a-input-password v-model:value="token" size="large" placeholder="STUDIO_ACCESS_TOKEN" />
        </a-form-item>
        <a-button type="primary" html-type="submit" size="large" block :loading="loading">
          进入工作台
        </a-button>
      </a-form>
    </a-card>
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  position: relative;
  overflow: hidden;
}
.box {
  width: min(440px, 100%);
  position: relative;
  z-index: 1;
}
.eyebrow {
  color: var(--teal);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.12em;
  margin-bottom: 10px;
}
h1 {
  margin: 0 0 8px;
  font-size: 34px;
}
p {
  color: var(--muted);
  margin: 0 0 22px;
}
</style>
