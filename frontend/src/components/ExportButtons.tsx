import { urlExportacao } from '../api/client'

export function ExportButtons({ sessionId }: { sessionId: string }) {
  return (
    <div className="export-buttons">
      <a className="botao botao--secundario" href={urlExportacao(sessionId, 'md')} download>
        Baixar Markdown
      </a>
      <a className="botao botao--primario" href={urlExportacao(sessionId, 'pdf')} download>
        Baixar PDF
      </a>
    </div>
  )
}
