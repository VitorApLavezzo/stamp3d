/**
 * Preview 3D do STL usando Three.js puro (sem @react-three/fiber)
 */

import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { Maximize2, RotateCcw } from 'lucide-react'
import clsx from 'clsx'

// ── STL PARSER ────────────────────────────────────────────────────────────
function parseSTL(buffer: ArrayBuffer): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry()
  const view = new DataView(buffer)

  // Detectar ASCII vs binário
  const header = new Uint8Array(buffer, 0, 5)
  const isBinary = !(header[0] === 115 && header[1] === 111 && header[2] === 108 && header[3] === 105 && header[4] === 100)

  const vertices: number[] = []
  const normals: number[] = []

  if (isBinary) {
    const triangleCount = view.getUint32(80, true)
    for (let i = 0; i < triangleCount; i++) {
      const offset = 84 + i * 50
      const nx = view.getFloat32(offset, true)
      const ny = view.getFloat32(offset + 4, true)
      const nz = view.getFloat32(offset + 8, true)
      for (let v = 0; v < 3; v++) {
        const vo = offset + 12 + v * 12
        vertices.push(view.getFloat32(vo, true), view.getFloat32(vo + 4, true), view.getFloat32(vo + 8, true))
        normals.push(nx, ny, nz)
      }
    }
  } else {
    const text = new TextDecoder().decode(buffer)
    const vertexRe = /vertex\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)/g
    const normalRe = /facet normal\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)/g
    let vm, nm
    const ns: number[][] = []
    while ((nm = normalRe.exec(text)) !== null)
      ns.push([parseFloat(nm[1]), parseFloat(nm[2]), parseFloat(nm[3])])
    let ti = 0
    while ((vm = vertexRe.exec(text)) !== null) {
      vertices.push(parseFloat(vm[1]), parseFloat(vm[2]), parseFloat(vm[3]))
      const n = ns[Math.floor(ti / 3)] || [0, 0, 1]
      normals.push(n[0], n[1], n[2])
      ti++
    }
  }

  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3))
  geometry.computeBoundingBox()
  return geometry
}

// ── COMPONENT ─────────────────────────────────────────────────────────────
interface Preview3DProps {
  stlUrl?: string
  isProcessing?: boolean
  className?: string
}

export function Preview3D({ stlUrl, isProcessing = false, className }: Preview3DProps) {
  const mountRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer
    scene: THREE.Scene
    camera: THREE.PerspectiveCamera
    mesh?: THREE.Mesh
    animId: number
    isDragging: boolean
    lastMouse: { x: number; y: number }
    rotX: number
    rotZ: number
    zoom: number
  } | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  // Init Three.js scene
  useEffect(() => {
    const el = mountRef.current
    if (!el) return

    const w = el.clientWidth || 600
    const h = el.clientHeight || 400

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(w, h)
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    el.appendChild(renderer.domElement)

    // Scene
    const scene = new THREE.Scene()

    // Camera
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 2000)
    camera.position.set(0, -120, 80)
    camera.lookAt(0, 0, 0)

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.5))
    const dir = new THREE.DirectionalLight(0xffffff, 1.5)
    dir.position.set(50, 50, 80)
    dir.castShadow = true
    scene.add(dir)
    const pt1 = new THREE.PointLight(0xf59e0b, 0.8, 300)
    pt1.position.set(-40, -40, 40)
    scene.add(pt1)

    // Grid
    const grid = new THREE.GridHelper(200, 20, 0xffffff, 0xffffff)
    grid.material.opacity = 0.05
    grid.material.transparent = true
    grid.rotation.x = Math.PI / 2
    scene.add(grid)

    // Placeholder cylinder (shown when no STL)
    const cylGeo = new THREE.CylinderGeometry(25, 25, 4, 64)
    cylGeo.rotateX(Math.PI / 2)
    const cylMat = new THREE.MeshPhysicalMaterial({
      color: 0xffffff, wireframe: true, opacity: 0.15, transparent: true
    })
    const placeholder = new THREE.Mesh(cylGeo, cylMat)
    placeholder.position.z = 2
    scene.add(placeholder)

    const state = {
      renderer, scene, camera,
      animId: 0,
      isDragging: false,
      lastMouse: { x: 0, y: 0 },
      rotX: 0.3,
      rotZ: 0,
      zoom: 1,
      placeholder
    }
    sceneRef.current = state as any

    // Animation loop
    let autoRot = 0
    const animate = () => {
      state.animId = requestAnimationFrame(animate)
      if (!state.isDragging) {
        autoRot += 0.005
        placeholder.rotation.z = autoRot
      }
      const pivot = new THREE.Object3D()
      camera.position.x = Math.sin(state.rotZ) * 120 * state.zoom
      camera.position.y = -Math.cos(state.rotZ) * 120 * state.zoom
      camera.position.z = 60 + state.rotX * 60
      camera.lookAt(0, 0, 15)
      renderer.render(scene, camera)
    }
    animate()

    // Mouse controls
    const onMouseDown = (e: MouseEvent) => {
      state.isDragging = true
      state.lastMouse = { x: e.clientX, y: e.clientY }
    }
    const onMouseMove = (e: MouseEvent) => {
      if (!state.isDragging) return
      const dx = e.clientX - state.lastMouse.x
      const dy = e.clientY - state.lastMouse.y
      state.rotZ += dx * 0.01
      state.rotX = Math.max(-1, Math.min(1, state.rotX - dy * 0.01))
      state.lastMouse = { x: e.clientX, y: e.clientY }
    }
    const onMouseUp = () => { state.isDragging = false }
    const onWheel = (e: WheelEvent) => {
      state.zoom = Math.max(0.3, Math.min(3, state.zoom + e.deltaY * 0.001))
    }

    el.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    el.addEventListener('wheel', onWheel, { passive: true })

    // Resize
    const onResize = () => {
      const w = el.clientWidth, h = el.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(state.animId)
      el.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      el.removeEventListener('wheel', onWheel)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement)
      sceneRef.current = null
    }
  }, [])

  // Load STL when URL changes
  useEffect(() => {
    if (!stlUrl || !sceneRef.current) return
    const state = sceneRef.current

    setLoaded(false)
    setError(false)

    fetch(stlUrl)
      .then(r => r.arrayBuffer())
      .then(buf => {
        if (!sceneRef.current) return
        const geo = parseSTL(buf)

        // Center geometry
        geo.computeBoundingBox()
        const box = geo.boundingBox!
        const cx = (box.max.x + box.min.x) / 2
        const cy = (box.max.y + box.min.y) / 2
        geo.translate(-cx, -cy, -box.min.z)

        // Remove old mesh
        if (state.mesh) {
          state.scene.remove(state.mesh)
          state.mesh.geometry.dispose()
        }

        const mat = new THREE.MeshPhysicalMaterial({
          color: 0xf59e0b,
          metalness: 0.1,
          roughness: 0.4,
          clearcoat: 0.3,
        })
        const mesh = new THREE.Mesh(geo, mat)
        mesh.castShadow = true
        state.scene.add(mesh)
        state.mesh = mesh
        setLoaded(true)
      })
      .catch(() => setError(true))
  }, [stlUrl])

  const handleReset = () => {
    if (!sceneRef.current) return
    sceneRef.current.rotX = 0.3
    sceneRef.current.rotZ = 0
    sceneRef.current.zoom = 1
  }

  return (
    <div className={clsx('relative rounded-2xl overflow-hidden bg-[#080810] border border-white/8', className)}>
      <div ref={mountRef} className="w-full h-full" style={{ minHeight: 300 }} />

      {/* Controls */}
      <div className="absolute top-3 right-3 flex gap-1.5">
        <button
          onClick={handleReset}
          className="w-7 h-7 rounded-lg bg-black/50 border border-white/10 flex items-center justify-center hover:bg-black/70 transition-colors"
          title="Resetar câmera"
        >
          <RotateCcw className="w-3.5 h-3.5 text-white/60" />
        </button>
      </div>

      {/* Status */}
      {!stlUrl && (
        <div className="absolute bottom-3 left-3 right-3 pointer-events-none">
          <div className="bg-black/60 backdrop-blur-sm rounded-xl px-3 py-2 border border-white/5 text-center">
            <p className="text-xs text-white/40">
              {isProcessing ? '⚙️ Gerando modelo 3D...' : '📦 Preview 3D aparecerá após o processamento'}
            </p>
          </div>
        </div>
      )}

      {stlUrl && loaded && (
        <div className="absolute bottom-3 left-3 pointer-events-none">
          <p className="text-[10px] text-white/20">🖱 Arraste para girar · Scroll para zoom</p>
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
