<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'
import {
  createI2vFromBatch,
  createI2vFromImages,
  listBatches,
  listSamples,
  mediaUrl,
  uploadI2vJsonl,
} from '@/api/client'
import type { Batch, Sample } from '@/types'
import { statusClass, statusLabel } from '@/utils/status'

const sourceBatchId = ref<string>()
const selected = ref<string[]>([])
const loading = ref(false)
const t2iBatches = ref<Batch[]>([])
const images = ref<Sample[]>([])
const batches = ref<Batch[]>([])
let timer: number | undefined

async function refresh() {
  ;[t2iBatches.value, images.value, batches.value] = await Promise.all([
    listBatches('t2i'),
    listSamples({ modality: 't2i', status: 'succeeded' }),
    listBatches('i2v'),
  ])
}

function toggle(id: string) {
  if (selected.value.includes(id)) {
    selected.value = selected.value.filter((item) => item !== id)
  } else {
    selected.value = [...selected.value, id]
  }
}

async function submitSelected() {
  loading.value = true
  try {
    const batch = await createI2vFromImages(selected.value)
    message.success(`已排队 ${batch.id}`)
    selected.value = []
    await refresh()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '提交失败')
  } finally {
    loading.value = false
  }
}

async function submitBatch() {
  if (!sourceBatchId.value) {
    message.warning('请先选择文生图批次')
    return
  }
  loading.value = true
  try {
    const batch = await createI2vFromBatch(sourceBatchId.value)
    message.success(`已排队 ${batch.id}`)
    await refresh()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '提交失败')
  } finally {
    loading.value = false
  }
}

const beforeUpload: UploadProps['beforeUpload'] = async (file) => {
  loading.value = true
  try {
    const batch = await uploadI2vJsonl(file as File)
    message.success(`已导入 ${batch.id}`)
    await refresh()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导入失败')
  } finally {
    loading.value = false
  }
  return false
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
      <h1 class="display">图生视频批次</h1>
      <p>每张已入库图片生成一条 9:16、3 秒视频。运动提示词来自该图保存的画面提示词。</p>
    </div>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="12">
        <a-card class="panel-card" title="整批送去图生视频" :bordered="false">
          <a-space direction="vertical" style="width: 100%" size="middle">
            <a-select
              v-model:value="sourceBatchId"
              allow-clear
              placeholder="选择文生图批次"
              style="width: 100%"
              :options="t2iBatches.map((batch) => ({
                value: batch.id,
                label: `${batch.id} · ${batch.requested_count} 条 · ${statusLabel(batch.status)}`,
              }))"
            />
            <a-button type="primary" :loading="loading" @click="submitBatch">送整批去图生视频</a-button>
          </a-space>
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card class="panel-card" title="JSONL 导入" :bordered="false">
          <a-upload-dragger :before-upload="beforeUpload" :show-upload-list="false" accept=".jsonl,.txt">
            <p class="ant-upload-drag-icon"><InboxOutlined /></p>
            <p class="ant-upload-text">每行需要 source_image_id</p>
            <p class="ant-upload-hint">可选 prompt 或 theme。</p>
          </a-upload-dragger>
        </a-card>
      </a-col>
    </a-row>

    <a-card class="panel-card" title="勾选已入库图片" :bordered="false" style="margin-top: 16px">
      <a-empty v-if="!images.length" description="还没有已入库的图片" />
      <a-row v-else :gutter="[12, 12]">
        <a-col v-for="image in images" :key="image.id" :xs="12" :sm="8" :md="6">
          <div
            class="media-tile"
            :class="{ selected: selected.includes(image.id) }"
            @click="toggle(image.id)"
          >
            <img :src="mediaUrl(image.id)" :alt="image.id" />
            <div class="cap">
              <div class="mono">{{ image.id }}</div>
              <a-checkbox :checked="selected.includes(image.id)" />
            </div>
          </div>
        </a-col>
      </a-row>
      <div style="margin-top: 16px">
        <a-button type="primary" :disabled="!selected.length" :loading="loading" @click="submitSelected">
          生成选中图片的视频（{{ selected.length }}）
        </a-button>
      </div>
    </a-card>

    <a-card class="panel-card" title="最近批次" :bordered="false" style="margin-top: 16px">
      <a-table :data-source="batches" :pagination="false" row-key="id" size="middle">
        <a-table-column title="批次 ID" data-index="id">
          <template #default="{ text }"><span class="mono">{{ text }}</span></template>
        </a-table-column>
        <a-table-column title="来源" data-index="source" :width="100" />
        <a-table-column title="数量" data-index="requested_count" :width="80" />
        <a-table-column title="状态" data-index="status" :width="120">
          <template #default="{ text }">
            <span class="status-pill" :class="statusClass(text)">{{ statusLabel(text) }}</span>
          </template>
        </a-table-column>
        <a-table-column title="创建时间" data-index="created_at" :width="220" />
      </a-table>
    </a-card>
  </div>
</template>

<style scoped>
.cap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  color: var(--muted);
  font-size: 12px;
}
</style>
