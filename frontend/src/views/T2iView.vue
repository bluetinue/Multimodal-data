<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'
import { createT2iTheme, listBatches, uploadT2iJsonl } from '@/api/client'
import type { Batch } from '@/types'
import { statusClass, statusLabel } from '@/utils/status'

const themeText = ref('')
const count = ref(1)
const loading = ref(false)
const batches = ref<Batch[]>([])
let timer: number | undefined

async function refresh() {
  batches.value = await listBatches('t2i')
}

async function submitTheme() {
  loading.value = true
  try {
    const batch = await createT2iTheme(themeText.value, count.value)
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
    const batch = await uploadT2iJsonl(file as File)
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
      <h1 class="display">文生图批次</h1>
      <p>主题交给 qwen38-27b-fp8 写成英文提示词，再按 1:1 的 Qwen Image 工作流渲染。</p>
    </div>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="14">
        <a-card class="panel-card" title="主题造数" :bordered="false">
          <a-form layout="vertical" @finish="submitTheme">
            <a-form-item label="主题" required>
              <a-textarea v-model:value="themeText" :rows="5" placeholder="例如：雨夜便利店门口的一个人" />
            </a-form-item>
            <a-form-item label="数量">
              <a-input-number v-model:value="count" :min="1" :max="200" style="width: 160px" />
            </a-form-item>
            <a-button type="primary" html-type="submit" :loading="loading">提交批次</a-button>
          </a-form>
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="10">
        <a-card class="panel-card" title="JSONL 导入" :bordered="false">
          <a-upload-dragger :before-upload="beforeUpload" :show-upload-list="false" accept=".jsonl,.txt">
            <p class="ant-upload-drag-icon"><InboxOutlined /></p>
            <p class="ant-upload-text">拖入或点击上传 JSONL</p>
            <p class="ant-upload-hint">有 prompt 直接渲染，只有 theme 则扩写。</p>
          </a-upload-dragger>
        </a-card>
      </a-col>
    </a-row>

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
