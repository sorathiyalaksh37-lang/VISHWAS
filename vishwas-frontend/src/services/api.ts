/**
 * api.ts
 *
 * HTTP client for the VISHWAS backend API.
 * Handles all communication with the FastAPI backend service.
 */

// ── API Configuration ──────────────────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

// ── Auth Token Management ──────────────────────────────────────────────────────

const TOKEN_KEY = 'vishwas:auth_token'

function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name?: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

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

export interface CategoryScores {
  identity: number | null
  request: number | null
  behavior: number | null
  channel: number | null
  voice: number | null
}

export interface Verification {
  action: string | null
  target: string | null
  safe_word_prompt: boolean | null
}

export interface SpeakerMatch {
  enrolled?: boolean
  similarity?: number | null
  claimed_contact?: string | null
  [key: string]: unknown
}

export interface VoiceEvidence {
  status: string | null
  spoof_prob: number | null
  windows_analyzed: number | null
  speaker_match: SpeakerMatch | null
  quality: Record<string, unknown> | null
  model: string | null
}

export interface AnalysisReportResponse {
  call_id: string
  status: string
  analysis_mode: 'mock' | 'real'
  language?: string | null
  transcript?: TranscriptResponse | null
  level: string
  score: number
  category_scores?: CategoryScores | null
  fired_rules?: string[]
  killchain_stage?: string | null
  verification?: Verification | null
  voice?: VoiceEvidence | null
  counterfactuals?: Array<{ change: string; new_score: number }> | null
  agent_findings: AgentFinding[]
  reasons: string[]
  recommended_actions: string[]
  warnings: string[]
  created_at: string
  completed_at?: string | null
}

export interface LiveSessionStartRequest {
  mode: 'webrtc' | 'cellular' | 'non_audio'
  audio_authorized?: boolean
  caller_number?: string
  claimed_identity?: string
  claimed_relationship?: string
}

export interface LiveSessionStartResponse {
  session_id: string
  mode: 'webrtc' | 'cellular' | 'non_audio'
  audio_authorized: boolean
  websocket_url: string
  created_at: string
}

export interface LiveTranscriptSegment {
  start: number
  end: number
  speaker: string
  text: string
  is_final: boolean
  confidence?: number
}

export interface LiveSessionState {
  session_id: string
  mode: 'webrtc' | 'cellular' | 'non_audio'
  state: 'active' | 'completed' | 'cancelled'
  audio_authorized: boolean
  caller_number?: string | null
  claimed_identity?: string | null
  claimed_relationship?: string | null
  current_score: number
  current_level: string
  voice_status: string
  voice_spoof_prob?: number | null
  windows_analyzed: number
  transcript_segments: LiveTranscriptSegment[]
  fired_rules: string[]
  reasons: string[]
  warnings: string[]
  recommended_actions: string[]
  created_at: string
}

export interface SubmitNonAudioMessageRequest {
  text: string
  speaker?: string
  timestamp_s?: number
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

export interface StreamSessionResponse {
  session_id: string
  status: string
  chunk_size_bytes: number
  format: string
  max_duration_minutes: number
  ttl_minutes: number
}

export interface StreamChunkResponse {
  status: string
  label: string
  spoof_prob: number | null
  confidence: string
  duration_analyzed_ms: number
  chunks_processed: number
}

export interface StreamDeleteResponse {
  session_id: string
  status: string
  message: string
}

// ── API Client ─────────────────────────────────────────────────────────────────

class APIClient {
  private baseURL: string

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  /**
   * Get headers for authenticated requests.
   */
  private getAuthHeaders(): Record<string, string> {
    const token = getAuthToken()
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    }
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    return headers
  }

  /**
   * Start a new voice detection streaming session.
   */
  async startVoiceStream(): Promise<StreamSessionResponse | null> {
    try {
      // Create demo auth headers if no token available
      const headers = this.getAuthHeaders()
      if (!headers['Authorization']) {
        console.warn('[API] No auth token, using demo mode')
        // In demo mode, backend should allow unauthenticated access or use a demo user
      }
      
      const response = await fetch(`${this.baseURL}/voice-detection/stream/start`, {
        method: 'POST',
        headers,
      })

      if (!response.ok) {
        console.error(`Start voice stream failed: ${response.status}`)
        if (response.status === 401) {
          console.error('Authentication required. Backend needs auth bypass for demo mode.')
        }
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Start voice stream error:', error)
      return null
    }
  }

  /**
   * Send an audio chunk to the streaming session.
   */
  async sendVoiceChunk(sessionId: string, chunk: Blob): Promise<StreamChunkResponse | null> {
    try {
      const formData = new FormData()
      // Add filename to help backend identify as a file upload
      formData.append('chunk', chunk, 'audio.raw')

      const token = getAuthToken()
      const headers: HeadersInit = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      // Don't set Content-Type - let browser set it with boundary for multipart/form-data

      console.log('[API] Sending chunk, size:', chunk.size, 'bytes, session:', sessionId)

      const response = await fetch(`${this.baseURL}/voice-detection/stream/${sessionId}/chunk`, {
        method: 'POST',
        headers,
        body: formData,
      })

      console.log('[API] Chunk response status:', response.status)

      if (response.status === 404) {
        // Session not found or expired
        const errorData = await response.json().catch(() => ({ detail: 'Session not found or expired' }))
        throw new Error(`404: ${errorData.detail || 'Session not found or expired'}`)
      }

      if (!response.ok) {
        const errorText = await response.text()
        console.error(`Send voice chunk failed: ${response.status}`, errorText)
        return null
      }

      const result = await response.json()
      console.log('[API] Chunk result:', result)
      return result
    } catch (error) {
      console.error('Send voice chunk error:', error)
      // Re-throw to allow component to handle specific error types
      throw error
    }
  }

  /**
   * Delete a streaming session (cleanup).
   */
  async deleteVoiceStream(sessionId: string): Promise<StreamDeleteResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/voice-detection/stream/${sessionId}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(),
      })

      if (!response.ok) {
        console.error(`Delete voice stream failed: ${response.status}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Delete voice stream error:', error)
      return null
    }
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

  // ── Authentication Methods ──────────────────────────────────────────────────

  /**
   * Login with email and password.
   */
  async login(email: string, password: string): Promise<AuthResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed' }))
        console.error('Login failed:', errorData)
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  /**
   * Register a new user.
   */
  async register(email: string, password: string, fullName?: string): Promise<AuthResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ 
          email, 
          password,
          full_name: fullName || null,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Registration failed' }))
        console.error('Registration failed:', errorData)
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('Registration error:', error)
      throw error
    }
  }

  /**
   * Get current user information.
   */
  async getCurrentUser(): Promise<User | null> {
    try {
      const response = await fetch(`${this.baseURL}/auth/me`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      })

      if (!response.ok) {
        console.error(`Get current user failed: ${response.status}`)
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Get current user error:', error)
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

      const token = getAuthToken()
      const headers: HeadersInit = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const response = await fetch(`${this.baseURL}/analyze/recording`, {
        method: 'POST',
        headers,
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
      const response = await fetch(`${this.baseURL}/call/${callId}/status`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
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
        headers: this.getAuthHeaders(),
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
      const response = await fetch(`${this.baseURL}/call/${callId}/state`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
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
          headers: this.getAuthHeaders(),
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

  /**
   * Derive WebSocket URL for live session analysis.
   */
  getLiveWebSocketUrl(sessionId?: string): string {
    const loc = window.location
    const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = this.baseURL.startsWith('http')
      ? this.baseURL.replace(/^https?:\/\//, '').split('/')[0]
      : loc.host
    const path = this.baseURL.startsWith('http')
      ? `${this.baseURL.replace(/^https?:\/\/[^/]+/, '')}/live/ws/analyze`
      : `${this.baseURL}/live/ws/analyze`
    const token = getAuthToken()
    let url = `${wsProto}//${host}${path}`
    const params: string[] = []
    if (token) params.push(`token=${encodeURIComponent(token)}`)
    if (sessionId) params.push(`session_id=${encodeURIComponent(sessionId)}`)
    if (params.length > 0) {
      url += `?${params.join('&')}`
    }
    return url
  }

  /**
   * Start a new live call fraud analysis session.
   */
  async startLiveSession(req: LiveSessionStartRequest): Promise<LiveSessionStartResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/live/sessions`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(req),
      })
      if (!response.ok) {
        console.error(`Start live session failed: ${response.status}`)
        return null
      }
      return await response.json()
    } catch (error) {
      console.error('Start live session error:', error)
      return null
    }
  }

  /**
   * Retrieve state of an active or recent live session.
   */
  async getLiveSessionState(sessionId: string): Promise<LiveSessionState | null> {
    try {
      const response = await fetch(`${this.baseURL}/live/sessions/${sessionId}`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      })
      if (!response.ok) return null
      return await response.json()
    } catch (error) {
      console.error('Get live session error:', error)
      return null
    }
  }

  /**
   * Submit a non-audio message during a live session.
   */
  async submitLiveMessage(sessionId: string, req: SubmitNonAudioMessageRequest): Promise<LiveSessionState | null> {
    try {
      const response = await fetch(`${this.baseURL}/live/sessions/${sessionId}/message`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(req),
      })
      if (!response.ok) return null
      return await response.json()
    } catch (error) {
      console.error('Submit live message error:', error)
      return null
    }
  }

  /**
   * Conclude and finalize a live session, persisting to database.
   */
  async stopLiveSession(sessionId: string): Promise<CallStatusResponse | null> {
    try {
      const response = await fetch(`${this.baseURL}/live/sessions/${sessionId}/stop`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      })
      if (!response.ok) return null
      return await response.json()
    } catch (error) {
      console.error('Stop live session error:', error)
      return null
    }
  }

  /**
   * Cancel and discard a live session.
   */
  async cancelLiveSession(sessionId: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseURL}/live/sessions/${sessionId}/cancel`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      })
      return response.status === 204
    } catch (error) {
      console.error('Cancel live session error:', error)
      return false
    }
  }
}

// ── Export singleton ───────────────────────────────────────────────────────────

export const apiClient = new APIClient(API_BASE_URL)
