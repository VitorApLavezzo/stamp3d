import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { 
  Download, RefreshCw, Trash2, ArrowLeft, 
  FileCode2, Package, AlertCircle, CheckCircle2,
  Clock, Loader2, ChevronRight
} from 'lucide-react'
import clsx from 'clsx'
import { stampApi, createStatusPoller, type Project, type ProjectStatus } from '../utils/api'
import { Preview3D } from '../components/Preview3D'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

const STATUS_CONFIG: Record<ProjectStatus, { label: string; color: string; bg: string; icon: any }> = {
  pending:       { label: 'Na fila',         color: 'text-white/50',    bg: 'bg-white/5',        icon: Clock },
  processing:    { label: 'Processando',     color: 'text-blue-400',    bg: 'bg-blue-500/10',    icon: Loader2 },
  vectorizing:   { label: 'Vetorizando',     color: 'text-violet-400',  bg: 'bg-violet-500/10',  icon: Loader2 },
  generating_3d: { label: 'Gerando 3D',      color: 'text-amber-400',   bg: 'bg-amber-500/10',   icon: Loader2 },
  completed:     { label: 'Concluído',       color: 'text-emerald-400', bg: 'bg-emerald-500/10', icon: CheckCircle2 },
  failed:        { label: 'Falhou',          color: 'text-red-400',     bg: 'bg-red-500/10',     icon: AlertCircle },
}

const ACTIVE_STATUSES: ProjectStatus[] = ['pending', 'processing', 'vectorizing', 'generating_3d']

export function ProjectPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectId = Number(id)
  
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [showLog, setShowLog] = useState(false)

  useEffect(() => {
    if (!projectId) return
    
    let stopPolling: (() => void) | null = null
    
    stampApi.getProject(projectId)
      .then(p => {
        setProject(p)
        setLoading(false)
        
        // Start polling if still processing
        if (ACTIVE_STATUSES.includes(p.status as ProjectStatus)) {
          stopPolling = createStatusPoller(projectId, setProject)
        }
      })
      .catch(err => {
        setError(err?.response?.data?.detail || 'Projeto não encontrado')
        setLoading(false)
      })
    
    return () => stopPolling?.()
  }, [projectId])

  // Re-start polling if project becomes active
  useEffect(() => {
    if (!project) return
    if (!ACTIVE_STATUSES.includes(project.status as ProjectStatus)) return
    
    const stop = createStatusPoller(projectId, setProject)
    return stop
  }, [project?.status])

  const handleReprocess = async () => {
    if (!project) return
    try {
      await stampApi.reprocess(project.id)
      setProject(prev => prev ? { ...prev, status: 'pending', progress: 0 } : prev)
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Erro ao reprocessar')
    }
  }

  const handleDelete = async () => {
    if (!project || !confirm('Remover este projeto?')) return
    setDeleting(true)
    try {
      await stampApi.deleteProject(project.id)
      navigate('/projects')
    } catch (err) {
      setDeleting(false)
      alert('Erro ao remover')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="p-8">
        <div className="rounded-2xl bg-red-500/8 border border-red-500/20 p-6 max-w-md">
          <AlertCircle className="w-5 h-5 text-red-400 mb-2" />
          <p className="text-sm text-red-300">{error || 'Projeto não encontrado'}</p>
          <Link to="/projects" className="text-xs text-white/40 hover:text-white/70 mt-3 inline-flex items-center gap-1">
            <ArrowLeft className="w-3 h-3" /> Voltar aos projetos
          </Link>
        </div>
      </div>
    )
  }

  const statusConfig = STATUS_CONFIG[project.status as ProjectStatus]
  const StatusIcon = statusConfig.icon
  const isActive = ACTIVE_STATUSES.includes(project.status as ProjectStatus)
  const isCompleted = project.status === 'completed'
  const isFailed = project.status === 'failed'

  const stlUrl = project.stl_url 
    ? `http://localhost:8000${project.stl_url}` 
    : undefined

  return (
    <div className="min-h-full p-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-white/30 mb-6">
        <Link to="/projects" className="hover:text-white/60 transition-colors">Projetos</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-white/60">{project.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">{project.name}</h1>
          <div className="flex items-center gap-3">
            <span className={clsx(
              'inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border',
              statusConfig.color,
              statusConfig.bg,
              'border-current/20'
            )}>
              <StatusIcon className={clsx('w-3 h-3', isActive && 'animate-spin')} />
              {statusConfig.label}
            </span>
            <span className="text-xs text-white/25">
              {format(new Date(project.created_at), "d 'de' MMMM 'às' HH:mm", { locale: ptBR })}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleReprocess}
            disabled={isActive}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-white/50 hover:text-white/80 bg-white/3 hover:bg-white/5 border border-white/8 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reprocessar
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-red-400/60 hover:text-red-400 bg-red-500/3 hover:bg-red-500/8 border border-red-500/10 transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Remover
          </button>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Left: 3D Preview */}
        <div className="col-span-3 space-y-4">
          <Preview3D
            stlUrl={stlUrl}
            isProcessing={isActive}
            className="aspect-video"
          />

          {/* Download buttons */}
          {isCompleted && (
            <div className="grid grid-cols-3 gap-3">
              <a
                href={stampApi.stlDownloadUrl(project.id)}
                download
                className="flex flex-col items-center gap-2 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/15 transition-all group"
              >
                <Package className="w-5 h-5 text-amber-400 group-hover:scale-110 transition-transform" />
                <div className="text-center">
                  <p className="text-xs font-semibold text-amber-400">STL</p>
                  <p className="text-[10px] text-amber-400/50">Para impressora</p>
                </div>
              </a>
              
              <a
                href={stampApi.svgDownloadUrl(project.id)}
                download
                className="flex flex-col items-center gap-2 p-4 rounded-xl bg-violet-500/10 border border-violet-500/20 hover:bg-violet-500/15 transition-all group"
              >
                <FileCode2 className="w-5 h-5 text-violet-400 group-hover:scale-110 transition-transform" />
                <div className="text-center">
                  <p className="text-xs font-semibold text-violet-400">SVG</p>
                  <p className="text-[10px] text-violet-400/50">Vetor editável</p>
                </div>
              </a>
              
              <a
                href={stampApi.zipDownloadUrl(project.id)}
                download
                className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/8 transition-all group"
              >
                <Download className="w-5 h-5 text-white/50 group-hover:scale-110 transition-transform" />
                <div className="text-center">
                  <p className="text-xs font-semibold text-white/60">ZIP</p>
                  <p className="text-[10px] text-white/30">Todos os arquivos</p>
                </div>
              </a>
            </div>
          )}

          {/* Progress bar (when processing) */}
          {isActive && (
            <div className="rounded-2xl border border-white/8 bg-white/2 p-5">
              <div className="flex justify-between text-xs mb-3">
                <span className="text-white/50">{project.current_step}</span>
                <span className="text-amber-400 font-mono">{Math.round(project.progress)}%</span>
              </div>
              <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-orange-400 rounded-full transition-all duration-700"
                  style={{ width: `${project.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Error message */}
          {isFailed && project.error_message && (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/8 p-5">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5" />
                <div>
                  <p className="text-sm text-red-300 font-medium mb-1">Erro no processamento</p>
                  <p className="text-xs text-red-400/70 font-mono">{project.error_message}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Details */}
        <div className="col-span-2 space-y-4">
          {/* Image comparison */}
          <div className="rounded-2xl border border-white/8 bg-white/2 p-4">
            <p className="text-xs text-white/30 uppercase tracking-widest mb-3">Imagens</p>
            <div className="grid grid-cols-2 gap-2">
              {project.original_image_url && (
                <div>
                  <p className="text-[10px] text-white/25 mb-1.5 text-center">Original</p>
                  <img
                    src={`http://localhost:8000${project.original_image_url}`}
                    alt="Original"
                    className="w-full rounded-lg object-contain h-28"
                    style={{ background: 'repeating-conic-gradient(#ffffff08 0% 25%, transparent 0% 50%) 0 0 / 12px 12px' }}
                  />
                </div>
              )}
              {project.processed_image_url && (
                <div>
                  <p className="text-[10px] text-white/25 mb-1.5 text-center">Processada</p>
                  <img
                    src={`http://localhost:8000${project.processed_image_url}`}
                    alt="Processada"
                    className="w-full rounded-lg object-contain h-28"
                    style={{ background: 'repeating-conic-gradient(#ffffff08 0% 25%, transparent 0% 50%) 0 0 / 12px 12px' }}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Parameters */}
          <div className="rounded-2xl border border-white/8 bg-white/2 p-4">
            <p className="text-xs text-white/30 uppercase tracking-widest mb-3">Parâmetros</p>
            <div className="space-y-2">
              {[
                ['Diâmetro', `${project.stamp_diameter}mm`],
                ['Base', `${project.base_height}mm`],
                ['Relevo', `${project.relief_height}mm`],
                ['Escala X/Y', `${project.scale_x} / ${project.scale_y}`],
                ['Escala Z', `${project.scale_z}`],
                ['Location Z', `${project.location_z}mm`],
                ['Esp. mín. linha', `${project.min_line_width}mm`],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between items-center py-1 border-b border-white/4 last:border-0">
                  <span className="text-xs text-white/35">{k}</span>
                  <span className="text-xs text-white/70 font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Processing Log */}
          {project.processing_log && (
            <div className="rounded-2xl border border-white/8 bg-white/2 p-4">
              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center justify-between w-full text-xs text-white/30 uppercase tracking-widest"
              >
                Log de processamento
                <ChevronRight className={clsx('w-3.5 h-3.5 transition-transform', showLog && 'rotate-90')} />
              </button>
              {showLog && (
                <div className="mt-3 max-h-48 overflow-y-auto">
                  <pre className="text-[10px] text-white/30 font-mono whitespace-pre-wrap leading-relaxed">
                    {project.processing_log}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Print tips */}
          {isCompleted && (
            <div className="rounded-2xl border border-amber-500/15 bg-amber-500/5 p-4">
              <p className="text-xs text-amber-400/60 uppercase tracking-widest mb-2">Dicas de Impressão</p>
              <ul className="space-y-1.5">
                {[
                  'Material: PETG alimentício ou PLA',
                  'Layer Height: 0.2mm',
                  'Infill: 20%',
                  'Perimeters: 3',
                  'Sem suportes necessários',
                ].map(tip => (
                  <li key={tip} className="text-[11px] text-amber-400/50 flex items-center gap-1.5">
                    <div className="w-1 h-1 rounded-full bg-amber-500/40" />
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
