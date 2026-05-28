/**
 * Preview 3D com Three.js puro - controles orbitais completos
 */
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import clsx from 'clsx'

function parseSTL(buffer: ArrayBuffer): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry()
  const view = new DataView(buffer)
  const header = new Uint8Array(buffer, 0, 5)
  const isASCII = String.fromCharCode(...header) === 'solid'
  const verts: number[] = [], normals: number[] = []

  if (!isASCII) {
    const n = view.getUint32(80, true)
    for (let i = 0; i < n; i++) {
      const o = 84 + i * 50
      const nx = view.getFloat32(o, true)
      const ny = view.getFloat32(o + 4, true)
      const nz = view.getFloat32(o + 8, true)
      for (let v = 0; v < 3; v++) {
        const vo = o + 12 + v * 12
        verts.push(view.getFloat32(vo, true), view.getFloat32(vo + 4, true), view.getFloat32(vo + 8, true))
        normals.push(nx, ny, nz)
      }
    }
  } else {
    const text = new TextDecoder().decode(buffer)
    const vr = /vertex\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)/g
    const nr = /facet normal\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)/g
    const ns: number[][] = []
    let m: RegExpExecArray | null
    while ((m = nr.exec(text)) !== null) ns.push([+m[1], +m[2], +m[3]])
    let ti = 0
    while ((m = vr.exec(text)) !== null) {
      verts.push(+m[1], +m[2], +m[3])
      const n = ns[Math.floor(ti / 3)] || [0, 0, 1]
      normals.push(n[0], n[1], n[2])
      ti++
    }
  }

  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3))
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3))
  geo.computeBoundingBox()
  return geo
}

interface Preview3DProps {
  stlUrl?: string
  isProcessing?: boolean
  className?: string
}

export function Preview3D({ stlUrl, isProcessing = false, className }: Preview3DProps) {
  const mountRef = useRef<HTMLDivElement>(null)
  const stateRef = useRef<any>(null)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    const el = mountRef.current
    if (!el) return

    const W = el.clientWidth || 600
    const H = el.clientHeight || 400

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 5000)

    // Luzes
    scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const dir = new THREE.DirectionalLight(0xffffff, 1.2)
    dir.position.set(60, 80, 60)
    dir.castShadow = true
    scene.add(dir)
    const pt = new THREE.PointLight(0xf59e0b, 0.5, 500)
    pt.position.set(-40, 40, 40)
    scene.add(pt)

    // Grid
    const grid = new THREE.GridHelper(300, 30, 0x333344, 0x222233)
    ;(grid.material as THREE.Material).opacity = 0.3
    ;(grid.material as THREE.Material).transparent = true
    scene.add(grid)

    // Placeholder
    const ph = new THREE.Mesh(
      new THREE.CylinderGeometry(20, 20, 5, 64),
      new THREE.MeshPhysicalMaterial({ color: 0xffffff, wireframe: true, opacity: 0.15, transparent: true })
    )
    scene.add(ph)

    // Estado orbital
    const s = {
      renderer, scene, camera, ph,
      mesh: null as THREE.Mesh | null,
      animId: 0,
      theta: Math.PI / 4,
      phi: Math.PI / 3,
      radius: 200,
      target: new THREE.Vector3(0, 25, 0),
      drag: false,
      button: 0,
      mx: 0, my: 0,
    }
    stateRef.current = s

    const updateCam = () => {
      s.camera.position.set(
        s.target.x + s.radius * Math.sin(s.phi) * Math.sin(s.theta),
        s.target.y + s.radius * Math.cos(s.phi),
        s.target.z + s.radius * Math.sin(s.phi) * Math.cos(s.theta)
      )
      s.camera.lookAt(s.target)
    }
    updateCam()

    let autoT = 0
    const animate = () => {
      s.animId = requestAnimationFrame(animate)
      if (!s.mesh) { autoT += 0.008; ph.rotation.y = autoT }
      renderer.render(scene, camera)
    }
    animate()

    // Mouse
    const onDown = (e: MouseEvent) => {
      s.drag = true; s.button = e.button; s.mx = e.clientX; s.my = e.clientY
      e.preventDefault()
    }
    const onMove = (e: MouseEvent) => {
      if (!s.drag) return
      const dx = e.clientX - s.mx, dy = e.clientY - s.my
      s.mx = e.clientX; s.my = e.clientY
      if (s.button === 0) {
        s.theta -= dx * 0.01
        s.phi = Math.max(0.05, Math.min(Math.PI - 0.05, s.phi - dy * 0.01))
      } else {
        const spd = s.radius * 0.001
        const right = new THREE.Vector3().crossVectors(
          s.camera.getWorldDirection(new THREE.Vector3()), new THREE.Vector3(0, 1, 0)
        ).normalize()
        s.target.addScaledVector(right, -dx * spd)
        s.target.y += dy * spd
      }
      updateCam()
    }
    const onUp = () => { s.drag = false }
    const onWheel = (e: WheelEvent) => {
      s.radius = Math.max(20, Math.min(1000, s.radius * (1 + e.deltaY * 0.001)))
      updateCam()
      e.preventDefault()
    }
    const onCtx = (e: Event) => e.preventDefault()
    const onResize = () => {
      const w = el.clientWidth, h = el.clientHeight
      camera.aspect = w / h; camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }

    el.addEventListener('mousedown', onDown)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('contextmenu', onCtx)
    window.addEventListener('resize', onResize)

    // Touch
    let lastDist = 0
    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        s.drag = true; s.button = 0
        s.mx = e.touches[0].clientX; s.my = e.touches[0].clientY
      } else if (e.touches.length === 2) {
        s.drag = false
        lastDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        )
      }
      e.preventDefault()
    }
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 1 && s.drag) {
        const dx = e.touches[0].clientX - s.mx, dy = e.touches[0].clientY - s.my
        s.mx = e.touches[0].clientX; s.my = e.touches[0].clientY
        s.theta -= dx * 0.01
        s.phi = Math.max(0.05, Math.min(Math.PI - 0.05, s.phi - dy * 0.01))
        updateCam()
      } else if (e.touches.length === 2) {
        const d = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        )
        s.radius = Math.max(20, Math.min(1000, s.radius * (lastDist / d)))
        lastDist = d
        updateCam()
      }
      e.preventDefault()
    }
    const onTouchEnd = () => { s.drag = false }

    el.addEventListener('touchstart', onTouchStart, { passive: false })
    el.addEventListener('touchmove', onTouchMove, { passive: false })
    el.addEventListener('touchend', onTouchEnd)

    return () => {
      cancelAnimationFrame(s.animId)
      el.removeEventListener('mousedown', onDown)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('contextmenu', onCtx)
      window.removeEventListener('resize', onResize)
      el.removeEventListener('touchstart', onTouchStart)
      el.removeEventListener('touchmove', onTouchMove)
      el.removeEventListener('touchend', onTouchEnd)
      renderer.dispose()
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement)
      stateRef.current = null
    }
  }, [])

  // Carregar STL
  useEffect(() => {
    if (!stlUrl || !stateRef.current) return
    const s = stateRef.current
    setLoaded(false); setError(false)

    fetch(stlUrl)
      .then(r => r.arrayBuffer())
      .then(buf => {
        if (!stateRef.current) return
        const geo = parseSTL(buf)
        geo.computeBoundingBox()
        const box = geo.boundingBox!
        const cx = (box.max.x + box.min.x) / 2
        const cy = (box.max.y + box.min.y) / 2
        geo.translate(-cx, -cy, -box.min.z)
        // Z-up → Y-up
        geo.rotateX(-Math.PI / 2)
        geo.computeBoundingBox()

        if (s.mesh) { s.scene.remove(s.mesh); s.mesh.geometry.dispose() }
        s.scene.remove(s.ph)

        const mesh = new THREE.Mesh(geo, new THREE.MeshPhysicalMaterial({
          color: 0xf59e0b, metalness: 0.05, roughness: 0.3, clearcoat: 0.4,
        }))
        mesh.castShadow = true
        s.scene.add(mesh)
        s.mesh = mesh

        // Ajustar câmera ao modelo
        const size = geo.boundingBox!.getSize(new THREE.Vector3()).length()
        s.radius = size * 1.4
        s.target.set(0, size * 0.25, 0)
        s.camera.position.set(
          s.target.x + s.radius * Math.sin(s.phi) * Math.sin(s.theta),
          s.target.y + s.radius * Math.cos(s.phi),
          s.target.z + s.radius * Math.sin(s.phi) * Math.cos(s.theta)
        )
        s.camera.lookAt(s.target)
        setLoaded(true)
      })
      .catch(() => setError(true))
  }, [stlUrl])

  const handleReset = () => {
    const s = stateRef.current; if (!s) return
    s.theta = Math.PI / 4; s.phi = Math.PI / 3
    s.target.set(0, s.mesh ? s.radius * 0.2 : 25, 0)
    s.camera.position.set(
      s.target.x + s.radius * Math.sin(s.phi) * Math.sin(s.theta),
      s.target.y + s.radius * Math.cos(s.phi),
      s.target.z + s.radius * Math.sin(s.phi) * Math.cos(s.theta)
    )
    s.camera.lookAt(s.target)
  }

  return (
    <div className={clsx('relative rounded-2xl overflow-hidden bg-[#080810] border border-white/8 select-none', className)}>
      <div ref={mountRef} className="w-full h-full" style={{ minHeight: 300 }} />

      <div className="absolute top-3 right-3 flex flex-col gap-1.5">
        <button onClick={handleReset}
          className="w-7 h-7 rounded-lg bg-black/60 border border-white/10 flex items-center justify-center hover:bg-black/80 transition-colors text-white/60 text-xs"
          title="Resetar câmera">⟳</button>
        <button
          onClick={() => { const s = stateRef.current; if (s) { s.radius = Math.max(20, s.radius * 0.75); s.camera.position.set(s.target.x+s.radius*Math.sin(s.phi)*Math.sin(s.theta),s.target.y+s.radius*Math.cos(s.phi),s.target.z+s.radius*Math.sin(s.phi)*Math.cos(s.theta)); s.camera.lookAt(s.target) } }}
          className="w-7 h-7 rounded-lg bg-black/60 border border-white/10 flex items-center justify-center hover:bg-black/80 transition-colors text-white/60 text-sm"
          title="Zoom in">+</button>
        <button
          onClick={() => { const s = stateRef.current; if (s) { s.radius = Math.min(1000, s.radius * 1.33); s.camera.position.set(s.target.x+s.radius*Math.sin(s.phi)*Math.sin(s.theta),s.target.y+s.radius*Math.cos(s.phi),s.target.z+s.radius*Math.sin(s.phi)*Math.cos(s.theta)); s.camera.lookAt(s.target) } }}
          className="w-7 h-7 rounded-lg bg-black/60 border border-white/10 flex items-center justify-center hover:bg-black/80 transition-colors text-white/60 text-sm"
          title="Zoom out">−</button>
      </div>

      {loaded && (
        <div className="absolute bottom-3 left-3 pointer-events-none">
          <p className="text-[10px] text-white/25">Esq: girar · Dir: mover · Scroll: zoom</p>
        </div>
      )}

      {!stlUrl && (
        <div className="absolute bottom-3 left-3 right-3 pointer-events-none">
          <div className="bg-black/60 backdrop-blur-sm rounded-xl px-3 py-2 border border-white/5 text-center">
            <p className="text-xs text-white/40">
              {isProcessing ? '⚙️ Gerando modelo 3D...' : '📦 Preview 3D aparecerá após o processamento'}
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-xs text-red-400/70">Erro ao carregar STL</p>
        </div>
      )}
    </div>
  )
}