import { useCallback, useRef, useState } from 'react'
import { FileAudioIcon, UploadCloudIcon, XCircleIcon } from 'lucide-react'

/**
 * Accepted MIME types → display label
 */
const ACCEPTED_TYPES: Record<string, string> = {
  'audio/wav': 'WAV',
  'audio/x-wav': 'WAV',
  'audio/mpeg': 'MP3',
  'audio/mp3': 'MP3',
  'audio/mp4': 'M4A',
  'audio/m4a': 'M4A',
  'audio/x-m4a': 'M4A',
}

const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a']

export function isAcceptedAudioFile(file: File): boolean {
  if (ACCEPTED_TYPES[file.type]) return true
  const name = file.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export interface AudioFileState {
  name: string
  size: number
  /** Non-null means the file was rejected. */
  error: string | null
}

interface AudioUploadProps {
  /** Unique HTML id for the file input — must be unique per page. */
  inputId: string
  fileState: AudioFileState | null
  onFileChange: (state: AudioFileState | null) => void
}

/**
 * Reusable drag-and-drop audio upload widget.
 *
 * Validation rules:
 *  - Must be WAV, MP3, or M4A (checked by MIME type then by extension)
 *  - Rejected files get an error state, not a silent ignore
 *  - No upload happens; the parent decides what to do with valid files
 */
export function AudioUpload({ inputId, fileState, onFileChange }: AudioUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function processFile(file: File) {
    if (!isAcceptedAudioFile(file)) {
      onFileChange({
        name: file.name,
        size: file.size,
        error: 'Unsupported file type. Please upload a WAV, MP3, or M4A file.',
      })
      return
    }
    onFileChange({ name: file.name, size: file.size, error: null })
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) processFile(file)
    // Reset so the same file can be re-selected after clearing
    e.target.value = ''
  }

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) processFile(file)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(true)
  }

  function handleDragLeave() {
    setDragging(false)
  }

  function clearFile() {
    onFileChange(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="audio-upload">
      {/* Drop zone */}
      <div
        className={`upload-drop-zone${dragging ? ' upload-drop-zone--dragging' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        role="region"
        aria-label="Drag and drop audio file here, or use the button below"
      >
        <UploadCloudIcon
          size={36}
          strokeWidth={1.25}
          className="upload-drop-zone__icon"
          aria-hidden="true"
        />
        <p className="upload-drop-zone__prompt">Drag &amp; drop an audio file here</p>
        <p className="upload-drop-zone__formats">
          Supported formats:&nbsp;
          <span className="upload-drop-zone__format-tag">WAV</span>
          <span className="upload-drop-zone__format-tag">MP3</span>
          <span className="upload-drop-zone__format-tag">M4A</span>
        </p>

        {/* Hidden native input */}
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept=".wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4,audio/m4a,audio/x-m4a"
          className="upload-input-hidden"
          aria-label="Choose audio file"
          onChange={handleInputChange}
        />
        <label htmlFor={inputId} className="upload-btn">
          Choose Audio File
        </label>
      </div>

      {/* File feedback */}
      {fileState && (
        <div
          className={`upload-feedback${fileState.error ? ' upload-feedback--error' : ' upload-feedback--ok'}`}
          role="alert"
        >
          <div className="upload-feedback__info">
            <FileAudioIcon size={15} aria-hidden="true" className="upload-feedback__file-icon" />
            <div className="upload-feedback__text">
              <span className="upload-feedback__name">{fileState.name}</span>
              <span className="upload-feedback__meta">
                {fileState.error ? (
                  <span className="upload-feedback__error">
                    <XCircleIcon size={12} aria-hidden="true" />
                    {fileState.error}
                  </span>
                ) : (
                  formatBytes(fileState.size)
                )}
              </span>
            </div>
          </div>
          <button
            className="upload-feedback__clear"
            onClick={clearFile}
            aria-label="Remove selected file"
          >
            <XCircleIcon size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
