import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { 
  Layers, 
  Plus, 
  FolderOpen, 
  Settings, 
  Cpu,
  ChevronRight
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/', label: 'Dashboard', icon: Cpu, exact: true },
  { to: '/new', label: 'Novo Carimbo', icon: Plus },
  { to: '/projects', label: 'Projetos', icon: FolderOpen },
]

export function Layout() {
  return (
    <div className="flex h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col border-r border-white/5 bg-[#0d0d14]">
        {/* Logo */}
        <div className="px-6 py-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Layers className="w-5 h-5 text-black" />
            </div>
            <div>
              <h1 className="font-bold text-white tracking-tight">Stamp3D</h1>
              <p className="text-[10px] text-white/30 uppercase tracking-widest">Carimbos para Doces</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group',
                  isActive
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : 'text-white/40 hover:text-white/80 hover:bg-white/5'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={clsx('w-4 h-4', isActive ? 'text-amber-400' : 'text-current')} />
                  <span className="flex-1">{label}</span>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 text-amber-500/60" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/5">
          <div className="px-3 py-2.5 rounded-xl bg-white/3 border border-white/5">
            <p className="text-[10px] text-white/25 uppercase tracking-widest mb-1">Pipeline</p>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <p className="text-xs text-white/50">Backend ativo</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
