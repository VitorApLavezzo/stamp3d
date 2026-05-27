/**
 * Cliente API - Comunicação com backend FastAPI
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 120_000,
})

// ── TIPOS ─────────────────────────────────────────────────────────────────

export type ProjectStatus =
  | 'pending'
  | 'processing'
  | 'vectorizing'
  | 'generating_3d'
  | 'completed'
  | 'failed'

export interface Project {
  id: number
  name: string
  status: ProjectStatus
  progress: number
  current_step: string
  error_message?: string
  original_image_path?: string
  processed_image_path?: string
  svg_path?: string
  stl_path?: string
  stamp_diameter: number
  base_height: number
  relief_height: number
  scale_x: number
  scale_y: number
  scale_z: number
  location_z: number
  min_line_width: number
  created_at: string
  updated_at: string
  original_image_url?: string
  processed_image_url?: string
  svg_url?: string
  stl_url?: string
  stl_download_url?: string
}

export interface UploadParams {
  file: File
  projectName?: string
  stampDiameter?: number
  baseHeight?: number
  reliefHeight?: number
  minLineWidth?: number
  autoProcess?: boolean
}

// ── API CALLS ─────────────────────────────────────────────────────────────

export const stampApi = {
  async upload(params: UploadParams, onProgress?: (pct: number) => void) {
    const form = new FormData()
    form.append('file', params.file)
    if (params.projectName) form.append('project_name', params.projectName)
    if (params.stampDiameter) form.append('stamp_diameter', String(params.stampDiameter))
    if (params.baseHeight) form.append('base_height', String(params.baseHeight))
    if (params.reliefHeight) form.append('relief_height', String(params.reliefHeight))
    if (params.minLineWidth) form.append('min_line_width', String(params.minLineWidth))
    form.append('auto_process', String(params.autoProcess ?? true))

    const response = await api.post('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
    })
    return response.data as { success: boolean; project: Project }
  },

  async getProject(id: number) {
    const response = await api.get(`/projects/${id}`)
    return response.data as Project
  },

  async listProjects(limit = 20, offset = 0) {
    const response = await api.get('/projects', { params: { limit, offset } })
    return response.data as { projects: Project[]; total: number }
  },

  async reprocess(id: number) {
    const response = await api.post(`/projects/${id}/reprocess`)
    return response.data
  },

  async deleteProject(id: number) {
    const response = await api.delete(`/projects/${id}`)
    return response.data
  },

  stlDownloadUrl(id: number) { return `${BASE_URL}/api/v1/export/stl/${id}` },
  svgDownloadUrl(id: number) { return `${BASE_URL}/api/v1/export/svg/${id}` },
  zipDownloadUrl(id: number) { return `${BASE_URL}/api/v1/export/zip/${id}` },
  fileUrl(path: string)      { return `${BASE_URL}/storage/${path}` },

  /**
   * Upload de SVG externo (gerado pelo ChatGPT) para um projeto existente.
   * Pula o processamento de imagem e vai direto para geração 3D.
   */
  async uploadSvg(projectId: number, svgFile: File) {
    const form = new FormData()
    form.append('file', svgFile)
    const response = await api.post(`/upload-svg/${projectId}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },
}

// ── STATUS POLLER ─────────────────────────────────────────────────────────

const TERMINAL_STATUSES: ProjectStatus[] = ['completed', 'failed']

/**
 * Faz polling do status de um projeto até ele terminar.
 * Para automaticamente em completed/failed ou após maxAttempts.
 * Retorna função para parar manualmente.
 */
export function createStatusPoller(
  projectId: number,
  onUpdate: (project: Project) => void,
  intervalMs = 2000,      // aumentado de 1500 para 2000ms
  maxAttempts = 300       // para após 10 minutos (300 * 2s)
) {
  let active = true
  let attempts = 0
  let timeoutId: ReturnType<typeof setTimeout>

  const poll = async () => {
    if (!active) return

    attempts++
    if (attempts > maxAttempts) {
      console.warn(`Poller #${projectId}: limite de tentativas atingido, parando.`)
      active = false
      return
    }

    try {
      const project = await stampApi.getProject(projectId)
      onUpdate(project)

      // Parar se chegou num status terminal
      if (TERMINAL_STATUSES.includes(project.status)) {
        active = false
        return
      }

      // Continuar polling
      if (active) {
        timeoutId = setTimeout(poll, intervalMs)
      }
    } catch (err: any) {
      // Parar polling em erros 404 (projeto deletado) ou 401/403
      const status = err?.response?.status
      if (status === 404 || status === 401 || status === 403) {
        console.warn(`Poller #${projectId}: erro ${status}, parando.`)
        active = false
        return
      }

      // Em outros erros de rede, tentar novamente com delay maior
      if (active) {
        timeoutId = setTimeout(poll, intervalMs * 3)
      }
    }
  }

  poll()

  return () => {
    active = false
    clearTimeout(timeoutId)
  }
}