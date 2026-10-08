import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Check, Star, Trash2, Pencil, Users } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, btnSecondary, card, input, badge } from "@/lib/styles";

const defaultForm = { name: "", price: 0, description: "", cuts_per_month: "", features: "", recommended: false };

export default function Plans() {
  const [plans, setPlans] = useState([]);
  const [subs, setSubs] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(defaultForm);

  const load = () => {
    api.get("/plans").then((r) => setPlans(r.data));
    api.get("/subscriptions").then((r) => setSubs(r.data));
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(defaultForm); setOpen(true); };
  const openEdit = (p) => { setEditing(p); setForm({ ...p, features: (p.features || []).join("\n") }); setOpen(true); };

  const save = async () => {
    if (!form.name) { toast.error("Informe o nome do plano."); return; }
    const payload = { ...form, price: Number(form.price), features: form.features.split("\n").map((f) => f.trim()).filter(Boolean) };
    try {
      if (editing) await api.put(`/plans/${editing.id}`, payload);
      else await api.post("/plans", payload);
      toast.success(editing ? "Plano atualizado" : "Plano criado");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const remove = async (id) => {
    try { await api.delete(`/plans/${id}`); toast.success("Plano removido"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const cancelSub = async (id) => {
    try { await api.delete(`/subscriptions/${id}`); toast.success("Assinatura cancelada"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const activeSubs = subs.filter((s) => s.status === "Ativo");

  return (
    <div>
      <PageHeader eyebrow="Assinaturas" title="Planos" subtitle="Planos de assinatura e assinantes ativos."
        action={<button data-testid="add-plan-btn" onClick={openNew} className={btnPrimary}><Plus className="h-4 w-4" /> Novo Plano</button>} />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="plans-grid">
        {plans.map((p) => (
          <div key={p.id} className={card + ` p-6 ${p.recommended ? "border-amber-500/50 shadow-amber-950/20" : ""}`} data-testid={`plan-card-${p.id}`}>
            {p.recommended && <div className={badge("bg-amber-500/10 text-amber-400 border-amber-500/30 mb-3")}><Star className="h-3 w-3 mr-1" /> Recomendado</div>}
            <div className="font-display text-2xl font-extrabold">{p.name}</div>
            <div className="text-sm text-muted-foreground mt-1">{p.description}</div>
            <div className="mt-4 flex items-end gap-1">
              <span className="font-display text-4xl font-extrabold text-amber-400">R$ {p.price}</span>
              <span className="text-muted-foreground text-sm mb-1">/mês</span>
            </div>
            <div className="text-xs text-amber-500/90 font-semibold mt-1">{p.cuts_per_month}</div>
            <ul className="mt-4 space-y-2">
              {(p.features || []).map((f, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-muted-foreground"><Check className="h-4 w-4 text-emerald-400 shrink-0" /> {f}</li>
              ))}
            </ul>
            <div className="flex gap-2 mt-5">
              <button data-testid={`edit-plan-${p.id}`} onClick={() => openEdit(p)} className={btnSecondary + " flex-1"}><Pencil className="h-4 w-4" /> Editar</button>
              <button data-testid={`delete-plan-${p.id}`} onClick={() => remove(p.id)} className="px-3 rounded-xl border border-border text-rose-400 hover:bg-rose-500/10"><Trash2 className="h-4 w-4" /></button>
            </div>
          </div>
        ))}
      </div>

      <div className={card + " mt-8"}>
        <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
          <Users className="h-5 w-5 text-amber-500" />
          <h3 className="font-display text-xl font-bold">Assinantes Ativos</h3>
          <span className={badge("bg-emerald-500/10 text-emerald-400 border-emerald-500/20 ml-2")}>{activeSubs.length}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="subscribers-table">
            <thead><tr className="text-left text-muted-foreground border-b border-border">
              <th className="px-5 py-3 font-semibold">Cliente</th><th className="px-5 py-3 font-semibold">Plano</th>
              <th className="px-5 py-3 font-semibold">Renovação</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 text-right font-semibold">Ação</th>
            </tr></thead>
            <tbody>
              {activeSubs.length === 0 && <tr><td colSpan={5} className="px-5 py-8 text-center text-muted-foreground">Nenhum assinante ativo ainda.</td></tr>}
              {activeSubs.map((s) => (
                <tr key={s.id} className="border-b border-border/50 hover:bg-secondary/30">
                  <td className="px-5 py-3 font-medium">{s.client_name}</td>
                  <td className="px-5 py-3">{s.plan_name} <span className="text-muted-foreground text-xs">(R$ {s.price})</span></td>
                  <td className="px-5 py-3">{s.renewal_date?.split("-").reverse().join("/")}</td>
                  <td className="px-5 py-3"><span className={badge("bg-emerald-500/10 text-emerald-400 border-emerald-500/20")}>{s.status}</span></td>
                  <td className="px-5 py-3 text-right"><button onClick={() => cancelSub(s.id)} className="text-rose-400 hover:underline text-xs">Cancelar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg bg-card border-border max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display text-2xl">{editing ? "Editar Plano" : "Novo Plano"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><label className="text-sm font-medium">Nome</label><input data-testid="plan-name-input" className={input + " mt-1"} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="text-sm font-medium">Preço (R$)</label><input data-testid="plan-price-input" type="number" className={input + " mt-1"} value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></div>
              <div><label className="text-sm font-medium">Cortes/mês</label><input className={input + " mt-1"} value={form.cuts_per_month} onChange={(e) => setForm({ ...form, cuts_per_month: e.target.value })} /></div>
            </div>
            <div><label className="text-sm font-medium">Descrição</label><input className={input + " mt-1"} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div><label className="text-sm font-medium">Benefícios (um por linha)</label><textarea className={input + " mt-1 min-h-[100px]"} value={form.features} onChange={(e) => setForm({ ...form, features: e.target.value })} /></div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.recommended} onChange={(e) => setForm({ ...form, recommended: e.target.checked })} className="accent-amber-500 h-4 w-4" /> Marcar como recomendado</label>
            <div className="flex justify-end gap-2">
              <button onClick={() => setOpen(false)} className={btnSecondary}>Cancelar</button>
              <button data-testid="save-plan-btn" onClick={save} className={btnPrimary}>Salvar</button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
