// DashboardPage.tsx
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Layers, CheckCircle2, Clock, AlertCircle, Zap, TrendingUp } from 'lucide-react'
import { stampApi, type Project } from '../utils/api'

export function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    stampApi.listProjects(10)
      .then(r => { setProjects(r.projects); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const completed = projects.filter(p => p.status === 'completed').length
  const failed = projects.filter(p => p.status === 'failed').length
  const processing = projects.filter(p => ['processing','vectorizing','generating_3d','pending'].includes(p.status)).length

  return (
    <div className="p-8">
      {/* Hero */}
      <div className="mb-10">
        <p className="text-xs text-amber-400/70 uppercase tracking-widest mb-1">Sistema Automático</p>
        <h1 className="text-3xl font-bold text-white mb-2">
          Stamp<span className="text-amber-400">3D</span>
        </h1>
        <p className="text-white/40 max-w-md">
          Transforme imagens em carimbos 3D para doces automaticamente. 
          Do upload ao STL em segundos.
        </p>
        <Link
          to="/new"
          className="inline-flex items-center gap-2 mt-5 px-5 py-2.5 bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold rounded-xl transition-all shadow-lg shadow-amber-500/20 hover:shadow-amber-500/30"
        >
          <Plus className="w-4 h-4" />
          Novo Carimbo
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-10">
        {[
          { label: 'Total', value: projects.length, icon: Layers, color: 'text-white/60' },
          { label: 'Concluídos', value: completed, icon: CheckCircle2, color: 'text-emerald-400' },
          { label: 'Em processo', value: processing, icon: Clock, color: 'text-amber-400' },
          { label: 'Falhas', value: failed, icon: AlertCircle, color: 'text-red-400' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-2xl border border-white/8 bg-white/2 p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-white/30 uppercase tracking-widest">{label}</p>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <p className="text-3xl font-bold text-white">{value}</p>
          </div>
        ))}
      </div>

      {/* Pipeline steps visual */}
      <div className="rounded-2xl border border-white/8 bg-white/2 p-6 mb-8">
        <p className="text-xs text-white/30 uppercase tracking-widest mb-5">Pipeline Automático</p>
        <div className="flex items-center gap-0">
          {[
            { label: 'Upload', emoji: '📤' },
            { label: 'Remove fundo', emoji: '✂️' },
            { label: 'Limpa', emoji: '🧹' },
            { label: 'Vetoriza', emoji: '📐' },
            { label: 'Gera 3D', emoji: '🗿' },
            { label: 'Exporta STL', emoji: '📦' },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center flex-1">
              <div className="flex-1 text-center">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto mb-2 text-lg">
                  {step.emoji}
                </div>
                <p className="text-[10px] text-white/35 text-center">{step.label}</p>
              </div>
              {i < arr.length - 1 && (
                <div className="text-white/15 text-xs px-1">→</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Recent projects */}
      {projects.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs text-white/30 uppercase tracking-widest">Projetos Recentes</p>
            <Link to="/projects" className="text-xs text-amber-400/70 hover:text-amber-400 transition-colors">
              Ver todos →
            </Link>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {projects.slice(0, 6).map(p => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </div>
      )}

      {!loading && projects.length === 0 && (
        <div className="text-center py-16 border border-dashed border-white/8 rounded-2xl">
          <Zap className="w-8 h-8 text-white/15 mx-auto mb-3" />
          <p className="text-sm text-white/30">Nenhum projeto ainda</p>
          <p className="text-xs text-white/20 mb-4">Envie sua primeira imagem para começar</p>
          <Link to="/new" className="text-xs text-amber-400/70 hover:text-amber-400 transition-colors">
            Criar primeiro carimbo →
          </Link>
        </div>
      )}
    </div>
  )
}


// ── PROJECTS LIST PAGE ────────────────────────────────────────────────────

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    stampApi.listProjects(50)
      .then(r => { setProjects(r.projects); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <p className="text-xs text-amber-400/70 uppercase tracking-widest mb-1">Histórico</p>
          <h1 className="text-2xl font-bold text-white">Projetos</h1>
        </div>
        <Link
          to="/new"
          className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold rounded-xl transition-all"
        >
          <Plus className="w-4 h-4" />
          Novo
        </Link>
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-white/5 bg-white/2 h-40 animate-pulse" />
          ))}
        </div>
      ) : projects.length > 0 ? (
        <div className="grid grid-cols-3 gap-4">
          {projects.map(p => <ProjectCard key={p.id} project={p} />)}
        </div>
      ) : (
        <div className="text-center py-20 border border-dashed border-white/8 rounded-2xl">
          <p className="text-white/30 text-sm">Nenhum projeto encontrado</p>
        </div>
      )}
    </div>
  )
}


// ── PROJECT CARD ──────────────────────────────────────────────────────────

function ProjectCard({ project }: { project: Project }) {
  const statusColors: Record<string, string> = {
    completed: 'text-emerald-400',
    failed: 'text-red-400',
    processing: 'text-blue-400',
    vectorizing: 'text-violet-400',
    generating_3d: 'text-amber-400',
    pending: 'text-white/30',
  }

  const statusLabels: Record<string, string> = {
    completed: 'Concluído',
    failed: 'Falhou',
    processing: 'Processando',
    vectorizing: 'Vetorizando',
    generating_3d: 'Gerando 3D',
    pending: 'Na fila',
  }

  const isActive = ['pending','processing','vectorizing','generating_3d'].includes(project.status)

  return (
    <Link
      to={`/projects/${project.id}`}
      className="group rounded-2xl border border-white/8 bg-white/2 hover:bg-white/4 hover:border-white/15 transition-all p-4 block"
    >
      {/* Image thumbnail */}
      <div className="rounded-xl overflow-hidden mb-3 h-24 bg-white/3 flex items-center justify-center">
        {project.processed_image_url ? (
          <img
            src={`http://localhost:8000${project.processed_image_url}`}
            alt={project.name}
            className="w-full h-full object-contain"
          />
        ) : project.original_image_url ? (
          <img
            src={`http://localhost:8000${project.original_image_url}`}
            alt={project.name}
            className="w-full h-full object-contain opacity-50"
          />
        ) : (
          <Layers className="w-6 h-6 text-white/15" />
        )}
      </div>

      <p className="text-sm font-medium text-white/80 group-hover:text-white transition-colors truncate mb-1">
        {project.name}
      </p>

      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-medium ${statusColors[project.status] || 'text-white/30'}`}>
          {statusLabels[project.status] || project.status}
        </span>
        <span className="text-[10px] text-white/20">
          #{project.id}
        </span>
      </div>

      {/* Progress bar for active */}
      {isActive && (
        <div className="mt-2 h-0.5 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-400 rounded-full transition-all duration-500"
            style={{ width: `${project.progress}%` }}
          />
        </div>
      )}
    </Link>
  )
}
