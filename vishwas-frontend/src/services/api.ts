/**
 * api.ts
 *
 * HTTP client for the VISHWAS backend API.
 * Handles all communication with the FastAPI backend service.
 */

// ── API Configuration ──────────────────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  service: string
  version: string
}

export interface UploadResponse {
  call_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  message: string
  analysis_mode: 'mock' | 'real'
}

export interface CallStatusResponse {
  call_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  completed_at?: string
  error?: string
}

export interface TranscriptSegment {
  speaker: string | null
  text: string
  start: number
  end: number
  language?: string
}

export interface TranscriptResponse {
  call_id: string
  language: string | null
  transcription_status: string
  segments: TranscriptSegment[]
  is_mock?: boolean
}

export interface AgentFinding {
  agent: string
  signal: string
  severity: string
  evidence_text: string
  start_time?: number | null
  end_time?: number | null
  confidence?: number | null
  source: string
}

export interface AnalysisReportResponse {
  call_id: string
  status: string
  analysis_mode: 'mock' | 'real'
  language?: string | null
  transcript?: TranscriptResponse | null
  level: string
  score: number
  category_scores?: Record<string, number | null> | null
  fired_rules?: string[]
  killchain_stage?: string | null
  verification?: Record<string, unknown> | null
  voice?: Record<string, unknown> | null
  counterfactuals?: Array<{ change: string; new_score: number }> | null
  agent_findings: AgentFinding[]
  reasons: string[]
  recommended_actions: string[]
  warnings: string[]
  created_at: string
  completed_at?: string | null
}

export interface CallListItem {
  call_id: string
  original_filename: string
  status: string
  created_at: string
  updated_at: string
}

export interface PaginationInfo {
  page: number
  page_size: number
  total: number
  pages: number
}

export interface CallListResponse {
  calls: CallListItem[]
  pagination: PaginationInfo
}

// ── API Client ─────────────────────────────────────────────────────────────────

class APIClient {
  private baseURL: string

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  /**
   * Check if the backend is healthy and reachable.
   */
  async checkHealth(): Promise<HealthResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })

      if (!response.ok) {
        console.error(`Health check failed: ${response.status} ${response.statusText}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Health check error:', error)
      return null
    }
  }

  /**
   * Upload an audio file for analysis.
   */
  async uploadRecording(file: File): Promise<UploadResponse | null> {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${this.baseURL}/calls`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
        console.error('Upload failed:', errorData)
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('Upload error:', error)
      return null
    }
  }

  /**
   * Get the status of a call analysis.
   */
  async getCallStatus(callId: string): Promise<CallStatusResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/calls/${callId}/status`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })

      if (!response.ok) {
        console.error(`Get status failed: ${response.status}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Get status error:', error)
      return null
    }
  }

  /**
   * Get the transcript for a completed call.
   */
  async getTranscript(callId: string): Promise<TranscriptResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/calls/${callId}/transcript`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })

      if (!response.ok) {
        console.error(`Get transcript failed: ${response.status}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Get transcript error:', error)
      return null
    }
  }

  /**
   * Get the full analysis report for a completed call.
   */
  async getReport(callId: string): Promise<AnalysisReportResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/calls/${callId}/report`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })

      if (response.status === 425) {
        // Analysis in progress
        return null
      }

      if (!response.ok) {
        console.error(`Get report failed: ${response.status}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Get report error:', error)
      return null
    }
  }

  /**
   * Get a list of all call recordings.
   */
  async listCalls(page: number = 1, pageSize: number = 20): Promise<CallListResponse | null> {
    try {
      const response = await fetch(
        `${this.baseURL}/calls?page=${page}&page_size=${pageSize}`,
        {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
        }
      )

      if (!response.ok) {
        console.error(`List calls failed: ${response.status}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('List calls error:', error)
      return null
    }
  }
}

// ── Export singleton ───────────────────────────────────────────────────────────

export const apiClient = new APIClient(API_BASE_URL)
