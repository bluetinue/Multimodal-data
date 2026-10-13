import type { SampleStatus } from '@/types'

export function statusClass(status: SampleStatus | string): string {
  if (status === 'succeeded' || status === 'done') return 'ok'
  if (status === 'failed') return 'bad'
  return 'warn'
}

export function statusLabel(status: SampleStatus | string): string {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '渲染中',
    succeeded: '已入库',
    failed: '失败',
    done: '已完成',
  }
  return map[status] || status
}
