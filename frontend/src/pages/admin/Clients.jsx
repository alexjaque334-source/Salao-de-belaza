import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Search, Star, Crown } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, btnSecondary, card, input, badge, tierColors } from "@/lib/styles";

const defaultForm = { name: "", phone: "", notes: "", birthdate: "" };

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(defaultForm);

  const load = () => api.get("/clients").then((r) => setClients(r.data));
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(defaultForm); setOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ name: c.name, phone: c.phone || "", notes: c.notes || "", birthdate: c.birthdate || "" }); setOpen(true); };

  const save = async () => {
    if (!form.name || !form.phone) { toast.error("Nome e telefone obrigatórios."); return; }
    try {
      if (editing) await api.put(`/clients/${editing.id}`, form);
      else await api.post("/clients", form);
      toast.success(editing ? "Cliente atualizado" : "Cliente cadastrado.");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const filtered = clients.filter((c) => `${c.name} ${c.phone}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <PageHeader eyebrow="CRM" title="Clientes" subtitle="Base de clientes, histórico e fidelidade."
        action={<button data-testid="add-client-btn" onClick={openNew} className={btnPrimary}><Plus className="h-4 w-4" /> Novo Cliente</button>} />

      <div className="relative mb-5 max-w-sm">
        <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input data-testid="client-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar cliente..." className={input + " pl-9"} />
      </div>

      <div className={card}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="clients-table">
            <thead>
              <tr className="text-left text-muted-foreground border-b border-border">
                <th className="px-5 py-3 font-semibold">Cliente</th>
                <th className="px-5 py-3 font-semibold">Contato</th>
                <th className="px-5 py-3 font-semibold">Tier</th>
                <th className="px-5 py-3 font-semibold">Pontos</th>
                <th className="px-5 py-3 font-semibold">Visitas</th>
                <th className="px-5 py-3 font-semibold">Plano</th>
                <th className="px-5 py-3 font-semibold text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={7} className="px-5 py-10 text-center text-muted-foreground">Nenhum cliente encontrado.</td></tr>}
              {filtered.map((c) => (
                <tr key={c.id} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`client-row-${c.id}`}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-full bg-amber-500/10 grid place-items-center font-bold text-amber-400">{c.name[0]?.toUpperCase()}</div>
                      <div className="font-medium">{c.name}</div>
                    </div>
                  </td>
                  <td className="px-5 py-3"><div>{c.phone || "—"}</div></td>
                  <td className="px-5 py-3"><span className={badge(tierColors[c.tier])}>{c.tier}</span></td>
                  <td className="px-5 py-3 font-semibold text-amber-400">{c.points}</td>
                  <td className="px-5 py-3">{c.visits}</td>
                  <td className="px-5 py-3">{c.plan_name ? <span className={badge("bg-emerald-500/10 text-emerald-400 border-emerald-500/20")}>{c.plan_name}</span> : <span className="text-muted-foreground text-xs">—</span>}</td>
                  <td className="px-5 py-3 text-right">
                    <button data-testid={`edit-client-${c.id}`} onClick={() => openEdit(c)} className="p-2 rounded-lg text-muted-foreground hover:text-amber-400 hover:bg-secondary"><Pencil className="h-4 w-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg bg-card border-border">
          <DialogHeader><DialogTitle className="font-display text-2xl">{editing ? "Editar Cliente" : "Novo Cliente"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><label className="text-sm font-medium">Nome</label><input data-testid="client-name-input" className={input + " mt-1"} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><label className="text-sm font-medium">Telefone</label><input className={input + " mt-1"} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
            <div><label className="text-sm font-medium">Data de Aniversário (Opcional)</label><input type="date" className={input + " mt-1"} value={form.birthdate} onChange={(e) => setForm({ ...form, birthdate: e.target.value })} /></div>
            <div><label className="text-sm font-medium">Observações</label><textarea className={input + " mt-1 min-h-[80px]"} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setOpen(false)} className={btnSecondary}>Cancelar</button>
              <button data-testid="save-client-btn" onClick={save} className={btnPrimary}>Salvar</button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
