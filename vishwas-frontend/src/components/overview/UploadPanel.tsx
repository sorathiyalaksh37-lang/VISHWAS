import { useState } from 'react'
import { FileAudioIcon } from 'lucide-react'
import { AudioUpload, type AudioFileState } from '../shared/AudioUpload'

/**
 * Overview-page upload panel.
 * Wraps the shared AudioUpload widget with panel chrome.
 * The full analysis workflow lives on the dedicated Analyse a Call page.
 */
export function UploadPanel() {
  const [fileState, setFileState] = useState<AudioFileState | null>(null)

  return (
    <section className="upload-panel" aria-labelledby="upload-panel-heading">
      <div className="upload-panel__header">
        <div className="upload-panel__icon" aria-hidden="true">
          <FileAudioIcon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h2 id="upload-panel-heading" className="upload-panel__title">
            Upload a Recording
          </h2>
          <p className="upload-panel__subtitle">
            Select or drag in a call recording. Use{' '}
            <strong style={{ color: 'var(--color-accent)', fontWeight: 600 }}>Analyse a Call</strong>{' '}
            in the sidebar to start a full analysis once the backend is connected.
          </p>
        </div>
      </div>

      <AudioUpload
        inputId="overview-audio-file-input"
        fileState={fileState}
        onFileChange={setFileState}
      />

      {/* Backend notice */}
      <p className="upload-notice" role="note">
        Analysis will be available when the backend is connected.
      </p>
    </section>
  )
}
