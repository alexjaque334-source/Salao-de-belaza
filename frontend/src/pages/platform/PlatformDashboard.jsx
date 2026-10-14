import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ShieldCheck, LogOut, Search, CheckCircle2, XCircle, Ban, RotateCcw, History, Store, Plus, Pencil, Power, Trash2, LayoutDashboard, CreditCard,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { platformApi } from "@/lib/platformApi";
import { apiError } from "@/lib/api";
import { btnPrimary, btnSecondary, card, input, badge, overline } from "@/lib/styles";

const STATUS_META = {
  active: { label: "Ativa", cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  pending: { label: "Pendente", cls: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  suspended: { label: "Suspensa", cls: "bg-rose-500/10 text-rose-400 border-rose-500/20" },
  rejected: { label: "Rejeitada", cls: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20" },
};
const FILTERS = [["", "Todas"], ["pending", "Pendentes"], ["active", "Ativas"], ["suspended", "Suspensas"], ["rejected", "Rejeitadas"]];
const SUBSCRIPTION_META = {
  active: { label: "Ativa", cls: STATUS_META.active.cls },
  pending: { label: "Pendente", cls: STATUS_META.pending.cls },
  past_due: { label: "Atrasada", cls: STATUS_META.suspended.cls },
  canceled: { label: "Cancelada", cls: STATUS_META.rejected.cls },
  suspended: { label: "Suspensa", cls: STATUS_META.suspended.cls },
  unassigned: { label: "Sem assinatura", cls: STATUS_META.rejected.cls },
};

export default function PlatformDashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({ active: 0, pending: 0, suspended: 0, rejected: 0, total: 0 });
  const [shops, setShops] = useState([]);
  const [filter, setFilter] = useState("");
  const [q, setQ] = useState("");
  const [reasonModal, setReasonModal] = useState(null); // {shop, action, status, label}
  const [reason, setReason] = useState("");
  const [historyShop, setHistoryShop] = useState(null);
  const [section, setSection] = useState("shops");
  const [plans, setPlans] = useState([]);
  const [planModal, setPlanModal] = useState(null);
  const [assignShop, setAssignShop] = useState(null);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [subscriptionShop, setSubscriptionShop] = useState(null);
  const [subscriptionStatus, setSubscriptionStatus] = useState("pending");
  const [planForm, setPlanForm] = useState({ name: "", monthly_price: "", description: "", max_professionals: 1, max_services: 1, max_client_plans: 1, pdf_reports: false, active: true });

  const load = async () => {
    try {
      const [s, list] = await Promise.all([
        platformApi.get("/platform/stats"),
        platformApi.get(`/platform/shops${filter ? `?status=${filter}` : ""}`),
      ]);
      setStats(s.data);
      setShops(list.data);
    } catch (e) {
      if (e?.response?.status === 401 || e?.response?.status === 403) {
        localStorage.removeItem("platform_token");
        navigate("/plataforma");
      }
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const loadPlans = async () => {
    try {
      const r = await platformApi.get("/platform/plans");
      setPlans(r.data);
    } catch (e) { toast.error(apiError(e)); }
  };
  useEffect(() => { if (section === "plans") loadPlans(); /* eslint-disable-next-line */ }, [section]);

  const openPlan = (plan = null) => {
    setPlanForm(plan ? {
      name: plan.name, monthly_price: plan.monthly_price, description: plan.description || "",
      max_professionals: plan.max_professionals ?? "", max_services: plan.max_services ?? "",
      max_client_plans: plan.max_client_plans ?? "", pdf_reports: !!plan.pdf_reports, active: plan.active,
    } : { name: "", monthly_price: "", description: "", max_professionals: 1, max_services: 1, max_client_plans: 1, pdf_reports: false, active: true });
    setPlanModal(plan || {});
  };

  const savePlan = async () => {
    const payload = {
      ...planForm,
      monthly_price: Number(planForm.monthly_price),
      max_professionals: planForm.max_professionals === "" ? null : Number(planForm.max_professionals),
      max_services: planForm.max_services === "" ? null : Number(planForm.max_services),
      max_client_plans: planForm.max_client_plans === "" ? null : Number(planForm.max_client_plans),
      pdf_reports: !!planForm.pdf_reports,
    };
    try {
      if (planModal?.id) await platformApi.put(`/platform/plans/${planModal.id}`, payload);
      else await platformApi.post("/platform/plans", payload);
      toast.success(planModal?.id ? "Plano atualizado" : "Plano criado");
      setPlanModal(null);
      loadPlans();
    } catch (e) { toast.error(apiError(e)); }
  };

  const openAssignPlan = async (shop) => {
    if (!plans.length) await loadPlans();
    setSelectedPlanId(shop.platform_plan_id || "");
    setAssignShop(shop);
  };

  const assignPlan = async () => {
    if (!selectedPlanId) return toast.error("Selecione um plano");
    try {
      await platformApi.put(`/platform/shops/${assignShop.id}/plan`, { plan_id: selectedPlanId });
      toast.success(`Plano atualizado para ${assignShop.name}`);
      setAssignShop(null);
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const saveSubscriptionStatus = async () => {
    try {
      await platformApi.patch(`/platform/shops/${subscriptionShop.id}/subscription-status`, { status: subscriptionStatus });
      toast.success(`Assinatura de ${subscriptionShop.name} atualizada`);
      setSubscriptionShop(null);
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const togglePlan = async (plan) => {
    try {
      await platformApi.patch(`/platform/plans/${plan.id}/status`, { active: !plan.active });
      toast.success(`Plano ${plan.active ? "desativado" : "ativado"}`);
      loadPlans();
    } catch (e) { toast.error(apiError(e)); }
  };

  const deletePlan = async (plan) => {
    if (!window.confirm(`Excluir o plano "${plan.name}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await platformApi.delete(`/platform/plans/${plan.id}`);
      toast.success("Plano excluído");
      loadPlans();
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const act = async (shop, endpoint, action, body = {}) => {
    try {
      await platformApi.post(`/platform/shops/${shop.id}/${endpoint}`, body);
      toast.success(`Barbearia ${shop.name}: ${action}`);
      setReasonModal(null); setReason("");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const openReason = (shop, action, endpoint, label) => { setReason(""); setReasonModal({ shop, endpoint, label }); };

  const filtered = shops.filter((s) =>
    !q || `${s.name} ${s.responsible_name} ${s.email} ${s.code}`.toLowerCase().includes(q.toLowerCase()));

  const logout = () => { localStorage.removeItem("platform_token"); navigate("/plataforma"); };

  const StatCard = ({ label, value, cls }) => (
    <div className={card + " p-5"}>
      <div className={overline}>{label}</div>
      <div className={`font-display text-3xl font-extrabold mt-2 ${cls}`}>{value}</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card/40 sticky top-0 z-30 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 grid place-items-center">
              <ShieldCheck className="h-4 w-4 text-zinc-950" />
            </div>
            <span className="font-display font-extrabold">Administração da Plataforma</span>
          </div>
          <button data-testid="platform-logout-btn" onClick={logout} className={btnSecondary}><LogOut className="h-4 w-4" /> Sair</button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 sm:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-6">
          <aside className={card + " p-3 h-fit lg:sticky lg:top-24"}>
            <div className="px-3 py-2 mb-2">
              <div className={overline}>Super Admin</div>
              <div className="font-display font-bold mt-1">Painel da plataforma</div>
            </div>
            <nav className="space-y-1">
              <button onClick={() => setSection("shops")} className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${section === "shops" ? "bg-amber-500/10 text-amber-400" : "text-muted-foreground hover:bg-secondary hover:text-foreground"}`}><LayoutDashboard className="h-4 w-4" /> Dashboard</button>
              <button onClick={() => setSection("plans")} className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${section === "plans" ? "bg-amber-500/10 text-amber-400" : "text-muted-foreground hover:bg-secondary hover:text-foreground"}`}><CreditCard className="h-4 w-4" /> Planos da plataforma</button>
            </nav>
          </aside>
          <section className="min-w-0">
        {section === "shops" ? <>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6" data-testid="platform-stats">
          <StatCard label="Total" value={stats.total} cls="" />
          <StatCard label="Ativas" value={stats.active} cls="text-emerald-400" />
          <StatCard label="Pendentes" value={stats.pending} cls="text-amber-400" />
          <StatCard label="Suspensas" value={stats.suspended} cls="text-rose-400" />
          <StatCard label="Rejeitadas" value={stats.rejected} cls="text-zinc-400" />
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard label="Assinaturas ativas" value={stats.subscriptions_active || 0} cls="text-emerald-400" />
          <StatCard label="Assinaturas pendentes" value={stats.subscriptions_pending || 0} cls="text-amber-400" />
          <StatCard label="Assinaturas atrasadas" value={stats.subscriptions_past_due || 0} cls="text-rose-400" />
          <div className={card + " p-5"}>
            <div className={overline}>MRR projetado</div>
            <div className="font-display text-3xl font-extrabold mt-2">R$ {Number(stats.projected_mrr || 0).toFixed(2).replace(".", ",")}</div>
            <div className="text-xs text-muted-foreground mt-1">Baseado nos planos ativos</div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 mb-5">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map(([val, lbl]) => (
              <button key={val} data-testid={`platform-filter-${val || "all"}`} onClick={() => setFilter(val)}
                className={`px-3.5 py-2 rounded-lg text-sm font-semibold border transition-all ${filter === val ? "bg-amber-500/10 text-amber-400 border-amber-500/30" : "bg-secondary text-muted-foreground border-border hover:text-foreground"}`}>
                {lbl}
              </button>
            ))}
          </div>
          <div className="relative ml-auto max-w-xs w-full">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input data-testid="platform-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar barbearia..." className={input + " pl-9"} />
          </div>
        </div>

        <div className={card}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="platform-shops-table">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="px-5 py-3 font-semibold">Barbearia</th>
                  <th className="px-5 py-3 font-semibold">Responsável</th>
                  <th className="px-5 py-3 font-semibold">CPF/CNPJ</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Plano</th>
                  <th className="px-5 py-3 font-semibold text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && <tr><td colSpan={8} className="px-5 py-10 text-center text-muted-foreground">Nenhuma barbearia.</td></tr>}
                {filtered.map((s) => {
                  const m = STATUS_META[s.status] || STATUS_META.pending;
                  return (
                    <tr key={s.id} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`platform-shop-row-${s.id}`}>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2 font-medium"><Store className="h-4 w-4 text-amber-500" /> {s.name}</div>
                        <div className="text-xs text-muted-foreground">Código: {s.code} · {s.created_at?.slice(0, 10)}</div>
                      </td>
                      <td className="px-5 py-3"><div>{s.responsible_name || "—"}</div><div className="text-xs text-muted-foreground">{s.email}</div></td>
                      <td className="px-5 py-3 font-mono text-xs">{s.cpf_cnpj || "—"}</td>
                      <td className="px-5 py-3"><span className={badge(m.cls)}>{m.label}</span></td>
                      <td className="px-5 py-3"><button onClick={() => openAssignPlan(s)} className="text-left hover:text-amber-400 transition-colors"><div className="font-medium">{s.platform_plan_name || "Sem plano"}</div><div className="text-xs text-muted-foreground">Clique para alterar o plano</div></button><button onClick={() => { setSubscriptionStatus(s.subscription_status || "pending"); setSubscriptionShop(s); }} className="block mt-1"><span className={badge((SUBSCRIPTION_META[s.subscription_status] || SUBSCRIPTION_META.unassigned).cls)}>{(SUBSCRIPTION_META[s.subscription_status] || SUBSCRIPTION_META.unassigned).label}</span></button></td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1 flex-wrap">
                          {s.status === "pending" && (
                            <>
                              <button data-testid={`approve-${s.id}`} onClick={() => act(s, "approve", "aprovada")} className="p-2 rounded-lg text-emerald-400 hover:bg-emerald-500/10" title="Aprovar"><CheckCircle2 className="h-4 w-4" /></button>
                              <button data-testid={`reject-${s.id}`} onClick={() => openReason(s, "reject", "reject", "Rejeitar")} className="p-2 rounded-lg text-rose-400 hover:bg-rose-500/10" title="Rejeitar"><XCircle className="h-4 w-4" /></button>
                            </>
                          )}
                          {s.status === "active" && (
                            <button data-testid={`suspend-${s.id}`} onClick={() => openReason(s, "suspend", "suspend", "Suspender")} className="p-2 rounded-lg text-rose-400 hover:bg-rose-500/10" title="Suspender"><Ban className="h-4 w-4" /></button>
                          )}
                          {(s.status === "suspended" || s.status === "rejected") && (
                            <button data-testid={`reactivate-${s.id}`} onClick={() => act(s, "reactivate", "reativada")} className="p-2 rounded-lg text-emerald-400 hover:bg-emerald-500/10" title="Reativar"><RotateCcw className="h-4 w-4" /></button>
                          )}
                          <button data-testid={`history-${s.id}`} onClick={() => setHistoryShop(s)} className="p-2 rounded-lg text-muted-foreground hover:bg-secondary" title="Histórico"><History className="h-4 w-4" /></button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        </> : <>
          <div className="flex items-center justify-between mb-5">
            <div><h2 className="font-display text-2xl font-extrabold">Planos da plataforma</h2><p className="text-sm text-muted-foreground mt-1">Defina preços e limites oferecidos às barbearias.</p></div>
            <button onClick={() => openPlan()} className={btnPrimary}><Plus className="h-4 w-4" /> Novo Plano</button>
          </div>
          <div className={card + " overflow-x-auto"}>
            <table className="w-full text-sm">
              <thead><tr className="text-left text-muted-foreground border-b border-border">
                <th className="px-5 py-3">Plano</th><th className="px-5 py-3">Mensalidade</th><th className="px-5 py-3">Profissionais</th><th className="px-5 py-3">Serviços</th><th className="px-5 py-3">Planos cliente</th><th className="px-5 py-3">PDF</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Ações</th>
              </tr></thead>
              <tbody>
                {plans.length === 0 && <tr><td colSpan={6} className="px-5 py-10 text-center text-muted-foreground">Nenhum plano cadastrado.</td></tr>}
                {plans.map((p) => <tr key={p.id} className="border-b border-border/50">
                  <td className="px-5 py-3"><div className="font-semibold">{p.name}</div><div className="text-xs text-muted-foreground">{p.description || "—"}</div></td>
                  <td className="px-5 py-3">R$ {Number(p.monthly_price).toFixed(2).replace(".", ",")}</td>
                  <td className="px-5 py-3">{p.max_professionals ?? "Ilimitado"}</td><td className="px-5 py-3">{p.max_services ?? "Ilimitado"}</td>
                  <td className="px-5 py-3">{p.max_client_plans ?? "Ilimitado"}</td><td className="px-5 py-3">{p.pdf_reports ? "Sim" : "Não"}</td>
                  <td className="px-5 py-3"><span className={badge(p.active ? STATUS_META.active.cls : STATUS_META.suspended.cls)}>{p.active ? "Ativo" : "Inativo"}</span></td>
                  <td className="px-5 py-3"><div className="flex justify-end gap-1">
                    <button onClick={() => openPlan(p)} className="p-2 rounded-lg hover:bg-secondary" title="Editar"><Pencil className="h-4 w-4" /></button>
                    <button onClick={() => togglePlan(p)} className="p-2 rounded-lg hover:bg-secondary" title={p.active ? "Desativar" : "Ativar"}><Power className="h-4 w-4" /></button>
                    <button onClick={() => deletePlan(p)} className="p-2 rounded-lg text-rose-400 hover:bg-rose-500/10" title="Excluir"><Trash2 className="h-4 w-4" /></button>
                  </div></td>
                </tr>)}
              </tbody>
            </table>
          </div>
        </>}
          </section>
        </div>
      </main>

      <Dialog open={!!subscriptionShop} onOpenChange={(o) => !o && setSubscriptionShop(null)}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader><DialogTitle className="font-display text-xl">Assinatura — {subscriptionShop?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><label className="text-sm font-medium">Status da assinatura</label>
              <select value={subscriptionStatus} onChange={(e) => setSubscriptionStatus(e.target.value)} className={input + " mt-1"}>
                <option value="active">Ativa</option><option value="pending">Pendente</option><option value="past_due">Atrasada</option><option value="suspended">Suspensa</option><option value="canceled">Cancelada</option>
              </select>
              <p className="text-xs text-muted-foreground mt-2">Controle manual temporário. Futuramente este status poderá ser atualizado automaticamente pelo provedor de pagamento.</p>
            </div>
            <div className="flex justify-end gap-2"><button onClick={() => setSubscriptionShop(null)} className={btnSecondary}>Cancelar</button><button onClick={saveSubscriptionStatus} className={btnPrimary}>Salvar status</button></div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!assignShop} onOpenChange={(o) => !o && setAssignShop(null)}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader><DialogTitle className="font-display text-xl">Plano — {assignShop?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><label className="text-sm font-medium">Plano da plataforma</label>
              <select value={selectedPlanId} onChange={(e) => setSelectedPlanId(e.target.value)} className={input + " mt-1"}>
                <option value="">Selecione um plano</option>
                {plans.filter((p) => p.active).map((p) => <option key={p.id} value={p.id}>{p.name} — R$ {Number(p.monthly_price).toFixed(2).replace(".", ",")}/mês</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-2"><button onClick={() => setAssignShop(null)} className={btnSecondary}>Cancelar</button><button onClick={assignPlan} className={btnPrimary}>Salvar plano</button></div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!planModal} onOpenChange={(o) => !o && setPlanModal(null)}>
        <DialogContent className="max-w-lg bg-card border-border">
          <DialogHeader><DialogTitle className="font-display text-xl">{planModal?.id ? "Editar Plano" : "Novo Plano"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><label className="text-sm font-medium">Nome</label><input value={planForm.name} onChange={(e) => setPlanForm({...planForm, name:e.target.value})} className={input + " mt-1"} /></div>
            <div><label className="text-sm font-medium">Descrição</label><textarea value={planForm.description} onChange={(e) => setPlanForm({...planForm, description:e.target.value})} className={input + " mt-1 min-h-[80px]"} /></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div><label className="text-sm font-medium">Mensalidade (R$)</label><input type="number" min="0" step="0.01" value={planForm.monthly_price} onChange={(e) => setPlanForm({...planForm, monthly_price:e.target.value})} className={input + " mt-1"} /></div>
              <div><label className="text-sm font-medium">Profissionais</label><input type="number" min="1" placeholder="Vazio = ilimitado" value={planForm.max_professionals} onChange={(e) => setPlanForm({...planForm, max_professionals:e.target.value})} className={input + " mt-1"} /></div>
              <div><label className="text-sm font-medium">Serviços</label><input type="number" min="1" placeholder="Vazio = ilimitado" value={planForm.max_services} onChange={(e) => setPlanForm({...planForm, max_services:e.target.value})} className={input + " mt-1"} /></div>
              <div><label className="text-sm font-medium">Planos para clientes</label><input type="number" min="1" placeholder="Vazio = ilimitado" value={planForm.max_client_plans} onChange={(e) => setPlanForm({...planForm, max_client_plans:e.target.value})} className={input + " mt-1"} /></div>
            </div>
            <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={planForm.pdf_reports} onChange={(e) => setPlanForm({...planForm, pdf_reports:e.target.checked})} /> Permitir exportação de relatório mensal em PDF</label>
            <div className="flex justify-end gap-2"><button onClick={() => setPlanModal(null)} className={btnSecondary}>Cancelar</button><button onClick={savePlan} className={btnPrimary}>Salvar</button></div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!reasonModal} onOpenChange={(o) => !o && setReasonModal(null)}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader><DialogTitle className="font-display text-xl">{reasonModal?.label} — {reasonModal?.shop?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Motivo (opcional)</label>
              <textarea data-testid="reason-input" value={reason} onChange={(e) => setReason(e.target.value)} className={input + " mt-1 min-h-[90px]"} placeholder="Descreva o motivo da decisão..." />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setReasonModal(null)} className={btnSecondary}>Cancelar</button>
              <button data-testid="confirm-reason-btn" onClick={() => act(reasonModal.shop, reasonModal.endpoint, `${reasonModal.label.toLowerCase()}a`, { reason })} className={btnPrimary}>Confirmar</button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!historyShop} onOpenChange={(o) => !o && setHistoryShop(null)}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader><DialogTitle className="font-display text-xl">Histórico — {historyShop?.name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {(!historyShop?.decision_history || historyShop.decision_history.length === 0) && (
              <div className="text-sm text-muted-foreground">Nenhuma decisão registrada ainda.</div>
            )}
            {(historyShop?.decision_history || []).slice().reverse().map((h, i) => (
              <div key={i} className="rounded-xl bg-secondary/40 border border-border p-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold capitalize">{h.action}</span>
                  <span className="text-xs text-muted-foreground">{h.at?.slice(0, 16).replace("T", " ")}</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">por {h.by}</div>
                {h.reason && <div className="text-sm mt-1.5">"{h.reason}"</div>}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
