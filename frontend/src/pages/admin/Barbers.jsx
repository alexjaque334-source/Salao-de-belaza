import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Scissors, Pencil, Trash2, Phone } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, btnSecondary, card, input, badge, WEEKDAYS, WEEKDAY_LABELS } from "@/lib/styles";

const emptyHours = WEEKDAYS.reduce((a, d) => ({ ...a, [d]: { start: "", end: "" } }), {});
const defaultForm = { name: "", specialty: "", phone: "", avatar: "", active: true, working_hours: { ...emptyHours } };

export default function Barbers() {
  const [barbers, setBarbers] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(defaultForm);

  const load = () => api.get("/barbers").then((r) => setBarbers(r.data));
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ ...defaultForm, working_hours: JSON.parse(JSON.stringify(emptyHours)) }); setOpen(true); };
  const openEdit = (b) => {
    setEditing(b);
    setForm({
      name: b.name, specialty: b.specialty || "", phone: b.phone || "", avatar: b.avatar || "",
      active: b.active, working_hours: { ...emptyHours, ...(b.working_hours || {}) },
    });
    setOpen(true);
  };

  const save = async () => {
    if (!form.name) { toast.error("Informe o nome."); return; }
    try {
      if (editing) await api.put(`/barbers/${editing.id}`, form);
      else await api.post("/barbers", form);
      toast.success(editing ? "Barbeiro atualizado" : "Barbeiro cadastrado");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const remove = async (id) => {
    try { await api.delete(`/barbers/${id}`); toast.success("Barbeiro removido"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const setHour = (day, field, val) =>
    setForm((f) => ({ ...f, working_hours: { ...f.working_hours, [day]: { ...f.working_hours[day], [field]: val } } }));

  return (
    <div>
      <PageHeader eyebrow="Equipe" title="Barbeiros" subtitle="Cadastro, horários de trabalho e desempenho."
        action={<button data-testid="add-barber-btn" onClick={openNew} className={btnPrimary}><Plus className="h-4 w-4" /> Novo Barbeiro</button>} />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="barbers-grid">
        {barbers.map((b) => (
          <div key={b.id} className={card + " p-5 hover:border-amber-500/40 transition-all"} data-testid={`barber-card-${b.id}`}>
            <div className="flex items-start gap-4">
              {b.avatar ? (
                <img src={b.avatar} alt={b.name} className="h-16 w-16 rounded-xl object-cover border border-border" />
              ) : (
                <div className="h-16 w-16 rounded-xl bg-amber-500/10 grid place-items-center"><Scissors className="h-7 w-7 text-amber-400" /></div>
              )}
              <div className="flex-1 min-w-0">
                <div className="font-display font-bold text-lg">{b.name}</div>
                <div className="text-sm text-amber-400">{b.specialty}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1 mt-1"><Phone className="h-3 w-3" /> {b.phone || "—"}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <span className={badge(b.active ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-zinc-500/10 text-zinc-400 border-zinc-500/20")}>
                {b.active ? "Ativo" : "Inativo"}
              </span>
              <span className={badge("bg-amber-500/10 text-amber-400 border-amber-500/20")}>{b.total_cuts || 0} cortes</span>
            </div>
            <div className="flex gap-2 mt-4">
              <button data-testid={`edit-barber-${b.id}`} onClick={() => openEdit(b)} className={btnSecondary + " flex-1"}><Pencil className="h-4 w-4" /> Editar</button>
              <button data-testid={`delete-barber-${b.id}`} onClick={() => remove(b.id)} className="px-3 rounded-xl border border-border text-rose-400 hover:bg-rose-500/10"><Trash2 className="h-4 w-4" /></button>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl bg-card border-border max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display text-2xl">{editing ? "Editar Barbeiro" : "Novo Barbeiro"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div><label className="text-sm font-medium">Nome</label><input data-testid="barber-name-input" className={input + " mt-1"} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><label className="text-sm font-medium">Especialidade</label><input data-testid="barber-specialty-input" className={input + " mt-1"} value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} /></div>
              <div><label className="text-sm font-medium">Telefone</label><input className={input + " mt-1"} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
              <div><label className="text-sm font-medium">Foto (URL)</label><input className={input + " mt-1"} value={form.avatar} onChange={(e) => setForm({ ...form, avatar: e.target.value })} /></div>
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} className="accent-amber-500 h-4 w-4" /> Barbeiro ativo</label>

            <div>
              <div className="text-sm font-semibold mb-2">Horário de Trabalho</div>
              <div className="space-y-2">
                {WEEKDAYS.map((d) => (
                  <div key={d} className="grid grid-cols-[90px_1fr_1fr] items-center gap-2">
                    <span className="text-sm text-muted-foreground">{WEEKDAY_LABELS[d]}</span>
                    <input type="time" data-testid={`barber-hours-${d}-start`} value={form.working_hours[d]?.start || ""} onChange={(e) => setHour(d, "start", e.target.value)} className="bg-input/60 border border-border rounded-lg px-2 py-1.5 text-sm outline-none" />
                    <input type="time" data-testid={`barber-hours-${d}-end`} value={form.working_hours[d]?.end || ""} onChange={(e) => setHour(d, "end", e.target.value)} className="bg-input/60 border border-border rounded-lg px-2 py-1.5 text-sm outline-none" />
                  </div>
                ))}
                <p className="text-xs text-muted-foreground">Deixe em branco para folga no dia.</p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setOpen(false)} className={btnSecondary}>Cancelar</button>
              <button data-testid="save-barber-btn" onClick={save} className={btnPrimary}>Salvar</button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
