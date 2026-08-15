import { exportUrl } from '../api/client'

export function ExportButtons({ sessionId }: { sessionId: string }) {
  return (
    <div className="export-buttons">
      <a className="btn btn--secondary" href={exportUrl(sessionId, 'md')} download>
        Baixar Markdown
      </a>
      <a className="btn btn--primary" href={exportUrl(sessionId, 'pdf')} download>
        Baixar PDF
      </a>
    </div>
  )
}
