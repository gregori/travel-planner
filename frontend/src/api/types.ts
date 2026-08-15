export type TipoFonte = 'real' | 'estimativa' | 'mock'
export type NivelConfianca = 'alta' | 'media' | 'baixa'

export interface Fonte {
  tipo: TipoFonte
  provedor: string
  url: string | null
  consultado_em: string
  confianca: NivelConfianca
  observacao: string | null
}

export interface TripBrief {
  origem: string | null
  destino: string | null
  data_ida: string | null
  data_volta: string | null
  mes_referencia: string | null
  duracao_dias: number | null
  datas_flexiveis: boolean
  adultos: number | null
  criancas_idades: number[]
  orcamento_total: string | null
  moeda_orcamento: string
  moeda_exibicao: string
  tolerancia_orcamento: number
  tipo_viagem: string | null
  interesses: string[]
  restricoes_alimentares: string[]
  restricoes_mobilidade: string | null
  outras_restricoes: string[]
  ritmo: 'leve' | 'moderado' | 'intenso'
  nacionalidade: string | null
  campos_inferidos: string[]
}

export interface Atividade {
  titulo: string
  descricao: string | null
  regiao: string | null
  duracao_min: number | null
  custo_estimado: string
  moeda: string
  fonte: Fonte | null
  horario: string | null
}

export interface Deslocamento {
  de_bloco: string
  para_bloco: string
  duracao_min: number
  modo: string
}

export interface DiaItinerario {
  dia: number
  data: string | null
  regiao: string
  manha: Atividade[]
  tarde: Atividade[]
  noite: Atividade[]
  deslocamentos: Deslocamento[]
  custo_estimado_dia: string
  observacao: string | null
}

export interface OpcaoVoo {
  companhia: string
  origem: string
  destino: string
  preco_min: string
  preco_max: string
  moeda: string
  duracao_horas: number | null
  escalas: number
  link: string | null
  recomendada: boolean
  justificativa: string | null
  fonte: Fonte
}

export interface OpcaoHospedagem {
  nome: string
  tipo: string
  preco_por_noite: string
  moeda: string
  localizacao: string
  avaliacao: number | null
  link: string | null
  recomendada: boolean
  justificativa: string | null
  fonte: Fonte
}

export interface SugestaoRefeicao {
  nome: string
  tipo_refeicao: string
  culinaria: string | null
  faixa_preco: string | null
  compatibilidade: string
  localizacao: string | null
  link: string | null
  fonte: Fonte
}

export interface Orcamento {
  voos: string
  hospedagem: string
  alimentacao: string
  passeios: string
  transporte_local: string
  contingencia: string
  total: string
  teto_informado: string | null
  diferenca: string | null
  dentro_do_teto: boolean
  alertas: string[]
  fontes: Fonte[]
}

export interface CotacaoCambio {
  moeda_origem: string
  moeda_destino: string
  taxa: string
  fonte: Fonte
}

export interface Checklist {
  documentos: string[]
  clima: string | null
  moeda_e_cambio: string | null
  tomada_adaptador: string | null
  o_que_levar: string[]
  requisitos_entrada: string[]
}

export interface TripPlan {
  brief: TripBrief
  resumo: string
  opcoes_voo: OpcaoVoo[]
  opcoes_hospedagem: OpcaoHospedagem[]
  itinerario: DiaItinerario[]
  refeicoes: SugestaoRefeicao[]
  orcamento: Orcamento
  cambio: CotacaoCambio | null
  checklist: Checklist
  fontes: Fonte[]
  avisos: string[]
  gerado_em: string
}

export interface ChatMessage {
  autor: 'usuario' | 'agente'
  texto: string
}

export interface ErroResposta {
  erro: {
    codigo: string
    mensagem: string
    recuperavel: boolean
  }
}
