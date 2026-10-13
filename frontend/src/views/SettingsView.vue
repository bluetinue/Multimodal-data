<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchSettings } from '@/api/client'
import type { Settings } from '@/types'

const settings = ref<Settings | null>(null)
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    settings.value = await fetchSettings()
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="page-head">
      <h1 class="display">设置</h1>
      <p>地址和口令来自环境变量，这里只展示，不在页面修改。</p>
    </div>

    <a-card class="panel-card" :loading="loading" :bordered="false">
      <a-descriptions v-if="settings" :column="1" bordered size="middle">
        <a-descriptions-item label="ComfyUI">
          <span class="mono">{{ settings.comfyui_url }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="ComfyUI 状态">
          <span class="status-pill" :class="settings.comfy.ok ? 'ok' : 'bad'">
            {{ settings.comfy.ok ? `在线 ${settings.comfy.version || ''}` : settings.comfy.error || '无法连接' }}
          </span>
        </a-descriptions-item>
        <a-descriptions-item label="设备">
          {{ settings.comfy.device || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="大模型">
          {{ settings.llm_version }} / {{ settings.llm_model }}
        </a-descriptions-item>
        <a-descriptions-item label="文生图工作流">
          <span class="mono">{{ settings.t2i_workflow }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="图生视频工作流">
          <span class="mono">{{ settings.i2v_workflow }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="访问口令">
          已配置，不在页面展示
        </a-descriptions-item>
      </a-descriptions>
    </a-card>
  </div>
</template>
