<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { listSamples, mediaUrl } from '@/api/client'
import type { Sample } from '@/types'
import { statusClass, statusLabel } from '@/utils/status'

const samples = ref<Sample[]>([])
const loading = ref(false)
let timer: number | undefined

async function refresh() {
  loading.value = true
  try {
    samples.value = await listSamples()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, 4000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="page-head">
      <h1 class="display">样本库</h1>
      <p>只有检查通过的样本会进入导出文件。</p>
    </div>

    <a-space style="margin-bottom: 16px">
      <a-button :loading="loading" @click="refresh">
        <ReloadOutlined />
        刷新
      </a-button>
      <a-button type="primary" href="/api/export">
        <DownloadOutlined />
        导出 JSONL
      </a-button>
    </a-space>

    <a-empty v-if="!samples.length" description="还没有样本" />
    <a-row v-else :gutter="[12, 12]">
      <a-col v-for="sample in samples" :key="sample.id" :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="panel-card media-tile" :bordered="false" size="small">
          <video
            v-if="sample.modality === 'i2v' && sample.file_path"
            :src="mediaUrl(sample.id)"
            controls
          />
          <img
            v-else-if="sample.file_path"
            :src="mediaUrl(sample.id)"
            :alt="sample.id"
          />
          <div v-else class="placeholder">无文件</div>
          <div class="meta">
            <div>
              <a-tag>{{ sample.modality }}</a-tag>
              <span class="status-pill" :class="statusClass(sample.status)">{{ statusLabel(sample.status) }}</span>
            </div>
            <div class="mono">{{ sample.id }}</div>
            <div>
              {{ sample.width || '-' }}×{{ sample.height || '-' }}
              <span v-if="sample.duration"> · {{ sample.duration }}s</span>
            </div>
            <div v-if="sample.error" class="err">{{ sample.error }}</div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.meta {
  padding: 10px 4px 2px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.placeholder {
  height: 160px;
  display: grid;
  place-items: center;
  color: var(--muted);
  background: #05090d;
}
.err {
  color: var(--rose);
}
</style>
