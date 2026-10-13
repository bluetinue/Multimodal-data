import axios, { type AxiosError } from 'axios'
import type { Batch, Modality, Sample, Settings } from '@/types'

const http = axios.create({
  baseURL: '/',
  withCredentials: true,
  timeout: 60000,
})

function detail(error: unknown): string {
  const ax = error as AxiosError<{ detail?: string }>
  return ax.response?.data?.detail || ax.message || '请求失败'
}

export async function checkSession(): Promise<boolean> {
  const { data } = await http.get<{ ok: boolean }>('/api/session')
  return data.ok
}

export async function login(token: string): Promise<void> {
  try {
    await http.post('/api/login', { token })
  } catch (error) {
    throw new Error(detail(error))
  }
}

export async function logout(): Promise<void> {
  await http.post('/api/logout')
}

export async function fetchSettings(): Promise<Settings> {
  const { data } = await http.get<Settings>('/api/settings')
  return data
}

export async function listBatches(modality?: Modality): Promise<Batch[]> {
  const { data } = await http.get<{ items: Batch[] }>('/api/batches', {
    params: modality ? { modality } : undefined,
  })
  return data.items
}

export async function listSamples(params?: {
  modality?: Modality
  status?: string
  batch_id?: string
}): Promise<Sample[]> {
  const { data } = await http.get<{ items: Sample[] }>('/api/samples', { params })
  return data.items
}

export async function createT2iTheme(theme: string, count: number): Promise<Batch> {
  try {
    const { data } = await http.post<Batch>('/api/batches/t2i', { theme, count })
    return data
  } catch (error) {
    throw new Error(detail(error))
  }
}

export async function uploadT2iJsonl(file: File): Promise<Batch> {
  const body = new FormData()
  body.append('file', file)
  try {
    const { data } = await http.post<Batch>('/api/batches/t2i/jsonl', body)
    return data
  } catch (error) {
    throw new Error(detail(error))
  }
}

export async function createI2vFromImages(imageIds: string[]): Promise<Batch> {
  try {
    const { data } = await http.post<Batch>('/api/batches/i2v', { image_ids: imageIds })
    return data
  } catch (error) {
    throw new Error(detail(error))
  }
}

export async function createI2vFromBatch(sourceBatchId: string): Promise<Batch> {
  try {
    const { data } = await http.post<Batch>('/api/batches/i2v/from-batch', {
      source_batch_id: sourceBatchId,
    })
    return data
  } catch (error) {
    throw new Error(detail(error))
  }
}

export async function uploadI2vJsonl(file: File): Promise<Batch> {
  const body = new FormData()
  body.append('file', file)
  try {
    const { data } = await http.post<Batch>('/api/batches/i2v/jsonl', body)
    return data
  } catch (error) {
    throw new Error(detail(error))
  }
}

export function mediaUrl(sampleId: string): string {
  return `/api/media/${sampleId}`
}
