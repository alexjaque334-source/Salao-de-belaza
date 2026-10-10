import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, CalendarDays, Users, Scissors, Crown, BadgeDollarSign,
  LogOut, Menu, X, BarChart3, ClipboardList,
} from "lucide-react";
import { useState } from "react";
import { ShopStatusScreen } from "@/components/ShopStatusScreen";

const adminNav = [
  { to: "/dashboard", label: "Visão Geral", icon: LayoutDashboard, testid: "nav-dashboard-tab" },
  { to: "/agendamentos", label: "Agendamentos", icon: CalendarDays, testid: "nav-agendamentos-tab" },
  { to: "/barbeiros", label: "Barbeiros", icon: Scissors, testid: "nav-barbeiros-tab" },
  { to: "/servicos", label: "Serviços", icon: ClipboardList, testid: "nav-servicos-tab" },
  { to: "/clientes", label: "Clientes", icon: Users, testid: "nav-clientes-tab" },
  { to: "/fidelizados", label: "Fidelizados", icon: Crown, testid: "nav-fidelizados-tab" },
  { to: "/planos", label: "Planos", icon: BadgeDollarSign, testid: "nav-planos-tab" },
  { to: "/relatorios", label: "Relatórios", icon: BarChart3, testid: "nav-relatorios-tab" },
];


export function Shell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const nav = adminNav;

  if (user.shop_status && user.shop_status !== "active") {
    return <ShopStatusScreen status={user.shop_status} shopName={user.shop_name} shopCode={user.shop_code} />;
  }

  const doLogout = () => {
    logout();
    navigate("/login");
  };

  const SidebarInner = (
    <div className="flex flex-col h-full">
      <div className="px-6 py-7 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 grid place-items-center shadow-lg shadow-amber-900/40">
            <Scissors className="h-5 w-5 text-zinc-950" />
          </div>
          <div>
            <div className="font-display font-extrabold text-lg leading-none tracking-tight">
              BARBER<span className="text-amber-500">STUDIO</span>
            </div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground mt-1 font-serif-accent" data-testid="shop-name-label">
              {user.shop_name || "Est. 2026"}
            </div>
          </div>
        </div>
        {user.shop_code && (
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[11px] font-semibold text-amber-400" data-testid="shop-code-badge">
            Código: {user.shop_code}
          </div>
        )}
      </div>

      <nav className="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            data-testid={item.testid}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all ${
                isActive
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent"
              }`
            }
          >
            <item.icon className="h-[18px] w-[18px]" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-border">
        <div className="px-3 py-2 mb-2">
          <div className="text-sm font-semibold truncate">{user.name}</div>
          <div className="text-xs text-muted-foreground truncate">{user.email}</div>
        </div>
        <button
          data-testid="logout-btn"
          onClick={doLogout}
          className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold text-muted-foreground hover:text-rose-400 hover:bg-rose-500/5 transition-all"
        >
          <LogOut className="h-[18px] w-[18px]" /> Sair
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-border bg-card/40 sticky top-0 h-screen">
        {SidebarInner}
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 bg-card border-r border-border">
            {SidebarInner}
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0">
        <header className="lg:hidden sticky top-0 z-40 flex items-center justify-between px-4 h-16 border-b border-border bg-card/80 backdrop-blur">
          <button data-testid="mobile-menu-btn" onClick={() => setOpen(true)} className="p-2">
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
          <span className="font-display font-bold">BARBER<span className="text-amber-500">STUDIO</span></span>
          <div className="w-8" />
        </header>
        <main className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
