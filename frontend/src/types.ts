export type Modality = 't2i' | 'i2v'
export type SampleStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'done'

export interface Batch {
  id: string
  modality: Modality
  status: SampleStatus
  source: string
  theme?: string | null
  requested_count: number
  source_batch_id?: string | null
  created_at: string
  samples?: Sample[]
}

export interface Sample {
  id: string
  batch_id: string
  modality: Modality
  seed?: number | null
  image_prompt?: string | null
  motion_prompt?: string | null
  source_image_id?: string | null
  theme?: string | null
  workflow_filename?: string | null
  comfy_prompt_id?: string | null
  file_path?: string | null
  width?: number | null
  height?: number | null
  duration?: number | null
  sha256?: string | null
  status: SampleStatus
  error?: string | null
  attempts?: number
  created_at: string
}

export interface Settings {
  comfyui_url: string
  llm_version: string
  llm_model: string
  t2i_workflow: string
  i2v_workflow: string
  token_configured: boolean
  comfy: {
    ok: boolean
    version?: string
    device?: string
    error?: string
  }
}
