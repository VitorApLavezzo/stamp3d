import { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import {
  Upload, ImageIcon, Settings2, ChevronRight,
  AlertCircle, Loader2, CheckCircle2, Zap, FileCode2, X
} from 'lucide-react'
import clsx from 'clsx'
import { stampApi, createStatusPoller, type Project } from '../utils/api'

const STATUS_LABELS: Record<string, string> = {
  pending: 'Na fila...',
  processing: 'Processando imagem',
  vectorizing: 'Vetorizando para SVG',
  generating_3d: 'Gerando modelo 3D',
  completed: 'Concluído!',
  failed: 'Falhou',
}

const PIPELINE_STEPS = [
  { id: 'upload',    label: 'Upload',           range: [0, 5] },
  { id: 'process',  label: 'Processar imagem',  range: [5, 20] },
  { id: 'vectorize',label: 'Vetorizar SVG',     range: [20, 50] },
  { id: 'generate', label: 'Gerar modelo 3D',   range: [50, 90] },
  { id: 'export',   label: 'Exportar STL',      range: [90, 100] },
]

export function NewStampPage() {
  const navigate = useNavigate()

  // Modo: 'auto' = pipeline completo, 'svg' = upload SVG direto
  const [mode, setMode] = useState<'auto' | 'svg'>('auto')

  // Upload imagem
  const [preview, setPreview] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [projectName, setProjectName] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Upload SVG
  const [svgFile, setSvgFile] = useState<File | null>(null)
  const [svgPreview, setSvgPreview] = useState<string | null>(null)

  // Settings
  const [showSettings, setShowSettings] = useState(false)
  const [diameter, setDiameter] = useState(50)
  const [baseHeight, setBaseHeight] = useState(4)
  const [reliefHeight, setReliefHeight] = useState(6)
  const [minLineWidth, setMinLineWidth] = useState(1.2)

  // Processing
  const [project, setProject] = useState<Project | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Dropzone imagem
  const onDropImage = useCallback((accepted: File[]) => {
    const f = accepted[0]; if (!f) return
    setFile(f); setError(null)
    setPreview(URL.createObjectURL(f))
    setProjectName(f.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))
    setProject(null)
  }, [])

  const { getRootProps: getImgProps, getInputProps: getImgInput, isDragActive: imgDrag } = useDropzone({
    onDrop: onDropImage,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg', '.webp'] },
    maxFiles: 1, maxSize: 50 * 1024 * 1024,
  })

  // Dropzone SVG
  const onDropSvg = useCallback((accepted: File[]) => {
    const f = accepted[0]; if (!f) return
    setSvgFile(f); setError(null)
    const reader = new FileReader()
    reader.onload = (e) => setSvgPreview(e.target?.result as string)
    reader.readAsText(f)
    if (!projectName) setProjectName(f.name.replace('.svg', '').replace(/[_-]/g, ' '))
  }, [projectName])

  const { getRootProps: getSvgProps, getInputProps: getSvgInput, isDragActive: svgDrag } = useDropzone({
    onDrop: onDropSvg,
    accept: { 'image/svg+xml': ['.svg'] },
    maxFiles: 1,
  })

  const handleProcess = async () => {
    if (mode === 'auto' && !file) return
    if (mode === 'svg' && (!file || !svgFile)) return

    setError(null); setIsUploading(true); setUploadProgress(0)

    try {
      const result = await stampApi.upload(
        {
          file: file!,
          projectName: projectName || file!.name,
          stampDiameter: diameter,
          baseHeight,
          reliefHeight,
          minLineWidth,
          autoProcess: mode === 'auto',
        },
        setUploadProgress
      )

      if (mode === 'svg' && svgFile) {
        await stampApi.uploadSvg(result.project.id, svgFile)
      }

      setIsUploading(false); setIsProcessing(true)
      setProject(result.project)

      const stop = createStatusPoller(result.project.id, (updated) => {
        setProject(updated)
        if (updated.status === 'completed') {
          stop(); setTimeout(() => navigate(`/projects/${updated.id}`), 1500)
        }
        if (updated.status === 'failed') {
          stop(); setIsProcessing(false)
          setError(updated.error_message || 'Processamento falhou')
        }
      })
    } catch (err: any) {
      setIsUploading(false); setIsProcessing(false)
      setError(err?.response?.data?.detail || err?.message || 'Erro no upload')
    }
  }

  useEffect(() => { return () => { if (preview) URL.revokeObjectURL(preview) } }, [preview])

  const canProcess = mode === 'auto' ? !!file : (!!file && !!svgFile)

  return (
    <div className="min-h-full p-8">
      <div className="mb-6">
        <p className="text-xs text-amber-400/70 uppercase tracking-widest mb-1">Pipeline</p>
        <h1 className="text-2xl font-bold text-white">Novo Carimbo</h1>
      </div>

      {/* Modo selector */}
      <div className="flex gap-2 mb-6 p-1 bg-white/3 rounded-xl border border-white/8 w-fit">
        <button onClick={() => setMode('auto')}
          className={clsx('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
            mode === 'auto' ? 'bg-amber-500 text-black' : 'text-white/40 hover:text-white/70')}>
          <Zap className="w-3.5 h-3.5" />Automático
        </button>
        <button onClick={() => setMode('svg')}
          className={clsx('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
            mode === 'svg' ? 'bg-violet-500 text-white' : 'text-white/40 hover:text-white/70')}>
          <FileCode2 className="w-3.5 h-3.5" />Usar SVG do ChatGPT
        </button>
      </div>

      <div className="grid grid-cols-2 gap-6 max-w-5xl">
        {/* Left */}
        <div className="space-y-4">

          {/* Upload imagem */}
          <div>
            <p className="text-xs text-white/30 uppercase tracking-widest mb-2">
              {mode === 'svg' ? '1. Imagem original (referência)' : 'Imagem'}
            </p>
            <div {...getImgProps()}
              className={clsx('relative rounded-2xl border-2 border-dashed cursor-pointer transition-all',
                imgDrag ? 'border-amber-400 bg-amber-500/5'
                : preview ? 'border-white/10 bg-white/2'
                : 'border-white/10 bg-white/2 hover:border-amber-400/50'
              )} style={{ minHeight: 200 }}>
              <input {...getImgInput()} />
              {preview ? (
                <div className="p-3">
                  <img src={preview} alt="Preview" className="w-full rounded-xl object-contain max-h-48"
                    style={{ background: 'repeating-conic-gradient(#ffffff08 0% 25%, transparent 0% 50%) 0 0 / 16px 16px' }} />
                  <p className="text-xs text-white/30 mt-2 px-1">{file?.name}</p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Upload className="w-6 h-6 text-white/30 mb-2" />
                  <p className="text-sm text-white/50">Arraste a imagem</p>
                  <p className="text-xs text-white/25">PNG, JPG, WEBP</p>
                </div>
              )}
            </div>
          </div>

          {/* Upload SVG */}
          {mode === 'svg' && (
            <div>
              <p className="text-xs text-white/30 uppercase tracking-widest mb-2">
                2. SVG gerado pelo ChatGPT
              </p>
              <div {...getSvgProps()}
                className={clsx('relative rounded-2xl border-2 border-dashed cursor-pointer transition-all',
                  svgDrag ? 'border-violet-400 bg-violet-500/5'
                  : svgFile ? 'border-violet-500/30 bg-violet-500/5'
                  : 'border-white/10 bg-white/2 hover:border-violet-400/50'
                )} style={{ minHeight: 120 }}>
                <input {...getSvgInput()} />
                {svgFile ? (
                  <div className="p-4 flex items-center gap-3">
                    <FileCode2 className="w-8 h-8 text-violet-400 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm text-violet-300 font-medium">{svgFile.name}</p>
                      <p className="text-xs text-violet-400/50">{(svgFile.size/1024).toFixed(1)}KB</p>
                    </div>
                    <button className="text-white/30 hover:text-white/70"
                      onClick={(e) => { e.stopPropagation(); setSvgFile(null); setSvgPreview(null) }}>
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <FileCode2 className="w-6 h-6 text-white/30 mb-2" />
                    <p className="text-sm text-white/50">Arraste o arquivo .svg</p>
                    <p className="text-xs text-white/25 mt-1">Gerado pelo ChatGPT</p>
                  </div>
                )}
              </div>
              {svgPreview && (
                <div className="rounded-xl bg-white p-3 mt-2">
                  <p className="text-xs text-gray-400 mb-1 text-center">Preview do SVG</p>
                  <div className="w-full flex items-center justify-center" style={{ height: 100 }}
                    dangerouslySetInnerHTML={{ __html: svgPreview }} />
                </div>
              )}
              {!svgFile && (
                <div className="rounded-xl border border-violet-500/15 bg-violet-500/5 p-4 mt-2">
                  <p className="text-xs text-violet-400/70 font-medium mb-2">Como usar:</p>
                  <ol className="space-y-1 text-xs text-violet-400/50 list-decimal list-inside">
                    <li>Envie sua imagem para o ChatGPT</li>
                    <li>Peça para gerar uma "line art SVG vetorial"</li>
                    <li>Baixe o SVG e faça upload aqui</li>
                  </ol>
                </div>
              )}
            </div>
          )}

          {/* Nome */}
          <div>
            <label className="block text-xs text-white/40 mb-1.5 uppercase tracking-wider">Nome do Projeto</label>
            <input type="text" value={projectName} onChange={e => setProjectName(e.target.value)}
              placeholder="ex: Carimbo Nota Musical"
              className="w-full bg-white/3 border border-white/8 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-amber-500/40 transition-all" />
          </div>

          {/* Settings */}
          <button onClick={() => setShowSettings(!showSettings)}
            className="flex items-center gap-2 text-xs text-white/40 hover:text-white/70 transition-colors">
            <Settings2 className="w-3.5 h-3.5" />
            Parâmetros avançados
            <ChevronRight className={clsx('w-3.5 h-3.5 transition-transform', showSettings && 'rotate-90')} />
          </button>

          {showSettings && (
            <div className="rounded-xl border border-white/8 bg-white/2 p-4 space-y-4">
              <p className="text-xs text-white/30 uppercase tracking-widest">Parâmetros do Carimbo</p>
              {[
                { label: 'Diâmetro (mm)', value: diameter, set: setDiameter, min: 15, max: 60, step: 1 },
                { label: 'Base (mm)', value: baseHeight, set: setBaseHeight, min: 2, max: 10, step: 0.5 },
                { label: 'Relevo (mm)', value: reliefHeight, set: setReliefHeight, min: 2, max: 15, step: 0.5 },
                { label: 'Esp. mín. linha (mm)', value: minLineWidth, set: setMinLineWidth, min: 0.8, max: 3, step: 0.1 },
              ].map(({ label, value, set, min, max, step }) => (
                <div key={label} className="flex items-center justify-between gap-4">
                  <label className="text-xs text-white/50 flex-1">{label}</label>
                  <div className="flex items-center gap-2">
                    <input type="range" min={min} max={max} step={step} value={value}
                      onChange={e => set(Number(e.target.value))} className="w-24 accent-amber-400" />
                    <span className="text-xs text-amber-400 w-8 text-right font-mono">{value}</span>
                  </div>
                </div>
              ))}
              <div className="pt-2 border-t border-white/5">
                <p className="text-[10px] text-white/20 uppercase tracking-widest mb-2">Padrão Blender</p>
                <div className="grid grid-cols-4 gap-2">
                  {[['Scale X','0.1'],['Scale Y','0.1'],['Scale Z','0.2'],['Loc Z','15mm']].map(([k,v]) => (
                    <div key={k} className="bg-white/3 rounded-lg px-2 py-1.5 text-center">
                      <p className="text-[9px] text-white/25">{k}</p>
                      <p className="text-xs text-white/60 font-mono">{v}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2.5 rounded-xl bg-red-500/8 border border-red-500/20 px-4 py-3">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-300">{error}</p>
            </div>
          )}

          <button onClick={handleProcess} disabled={!canProcess || isUploading || isProcessing}
            className={clsx('w-full py-3.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2.5 transition-all',
              canProcess && !isUploading && !isProcessing
                ? mode === 'svg'
                  ? 'bg-violet-500 hover:bg-violet-400 text-white shadow-lg shadow-violet-500/20'
                  : 'bg-amber-500 hover:bg-amber-400 text-black shadow-lg shadow-amber-500/20'
                : 'bg-white/5 text-white/20 cursor-not-allowed')}>
            {isUploading ? <><Loader2 className="w-4 h-4 animate-spin" />Enviando... {uploadProgress}%</>
             : isProcessing ? <><Loader2 className="w-4 h-4 animate-spin" />Processando...</>
             : mode === 'svg' ? <><FileCode2 className="w-4 h-4" />Gerar 3D com meu SVG</>
             : <><Zap className="w-4 h-4" />Gerar Automaticamente</>}
          </button>
        </div>

        {/* Right: pipeline */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-white/8 bg-white/2 p-6">
            <p className="text-xs text-white/30 uppercase tracking-widest mb-5">
              {mode === 'svg' ? 'Pipeline (SVG → 3D)' : 'Pipeline Automático'}
            </p>
            <div className="space-y-3">
              {(mode === 'svg'
                ? [
                    { label: 'Upload imagem + SVG', range: [0, 10] },
                    { label: 'Gerar modelo 3D',     range: [10, 90] },
                    { label: 'Exportar STL',         range: [90, 100] },
                  ]
                : PIPELINE_STEPS
              ).map((step, idx) => {
                const progress = project?.progress ?? 0
                const isDone   = progress >= step.range[1]
                const isActive = !isDone && progress >= step.range[0]
                return (
                  <div key={idx} className="flex items-center gap-3">
                    <div className={clsx('w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0',
                      isDone   ? 'bg-emerald-500/20 border border-emerald-500/40'
                      : isActive ? 'bg-amber-500/20 border border-amber-500/40'
                      : 'bg-white/3 border border-white/8')}>
                      {isDone   ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                       : isActive ? <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />
                       : <div className="w-1.5 h-1.5 rounded-full bg-white/20" />}
                    </div>
                    <p className={clsx('text-sm', isDone ? 'text-white/60' : isActive ? 'text-white' : 'text-white/25')}>
                      {step.label}
                    </p>
                  </div>
                )
              })}
            </div>

            {(isProcessing || isUploading) && (
              <div className="mt-6">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-white/40">{project?.current_step || 'Aguardando...'}</span>
                  <span className="text-amber-400 font-mono">
                    {isUploading ? uploadProgress : Math.round(project?.progress ?? 0)}%
                  </span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-amber-500 to-orange-400 rounded-full transition-all duration-700"
                    style={{ width: `${isUploading ? uploadProgress * 0.05 : (project?.progress ?? 0)}%` }} />
                </div>
              </div>
            )}

            {project?.status === 'completed' && (
              <div className="mt-6 rounded-xl bg-emerald-500/8 border border-emerald-500/20 px-4 py-3 flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <p className="text-sm text-emerald-400 font-medium">STL gerado! Redirecionando...</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}