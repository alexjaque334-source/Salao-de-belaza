import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2, XCircle, Filter, MessageCircle, Share2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { BookingWizard } from "@/components/BookingWizard";
import { btnPrimary, btnGhost, card, badge, statusColors } from "@/lib/styles";

const STATUSES = ["Confirmado", "Concluído", "Cancelado", "Não Compareceu"];

function whatsappUrl(a) {
  let digits = (a.client_phone || "").replace(/\D/g, "");
  if (!digits) return null;
  if (digits.length <= 11 && !digits.startsWith("55")) digits = "55" + digits;
  const nome = (a.client_name || "").split(" ")[0];
  const dataBr = a.date.split("-").reverse().join("/");
  const msg = `Olá ${nome}! 👋 Lembrete do seu horário na BarberStudio: ${a.service_name} com ${a.barber_name} em ${dataBr} às ${a.time}. Qualquer coisa é só responder por aqui. Até lá! ✂️`;
  return `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`;
}

export default function Appointments() {
  const [appts, setAppts] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [filterBarber, setFilterBarber] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterDate, setFilterDate] = useState("");
  const [open, setOpen] = useState(false);
  const [publicLink, setPublicLink] = useState("");

  const load = () => api.get("/appointments").then((r) => setAppts(r.data));
  useEffect(() => {
    load();
    api.get("/barbers").then((r) => setBarbers(r.data));
    api.get("/shop/public-link")
      .then((r) => setPublicLink(new URL(r.data.path, window.location.origin).toString()))
      .catch((e) => toast.error(apiError(e)));
  }, []);

  const sharePublicLink = async () => {
    try {
      if (navigator.share) {
        await navigator.share({ title: "Agendamento online", url: publicLink });
        toast.success("Link compartilhado.");
        return;
      }
      if (!navigator.clipboard?.writeText) throw new Error("Compartilhamento indisponível neste navegador.");
      await navigator.clipboard.writeText(publicLink);
      toast.success("Link público copiado.");
    } catch (e) {
      if (e?.name !== "AbortError") toast.error(e?.message || "Não foi possível compartilhar o link.");
    }
  };

  const setStatus = async (id, status) => {
    try {
      await api.patch(`/appointments/${id}/status`, { status });
      toast.success("Status atualizado");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const remove = async (id) => {
    try {
      await api.delete(`/appointments/${id}`);
      toast.success("Agendamento removido");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const filtered = appts.filter(
    (a) =>
      (!filterBarber || a.barber_id === filterBarber) &&
      (!filterStatus || a.status === filterStatus) &&
      (!filterDate || a.date === filterDate)
  );

  return (
    <div>
      <PageHeader
        eyebrow="Agenda"
        title="Agendamentos"
        subtitle="Gerencie a agenda de todos os barbeiros."
        action={
          <div className="flex items-center gap-2">
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <button data-testid="new-appointment-btn" className={btnPrimary}><Plus className="h-4 w-4" /> Novo Agendamento</button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl bg-card border-border">
                <DialogHeader><DialogTitle className="font-display text-2xl">Novo Agendamento</DialogTitle></DialogHeader>
                <BookingWizard isAdmin onBooked={() => { setOpen(false); load(); }} />
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {publicLink && (
        <div className="flex justify-end mb-5">
          <button type="button" onClick={sharePublicLink} className="inline-flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm font-semibold text-amber-400 transition-all hover:bg-amber-500/20" title="Compartilhar ou copiar link público de agendamento">
            <Share2 className="h-4 w-4" /> Compartilhar link público
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-2 text-muted-foreground text-sm"><Filter className="h-4 w-4" /> Filtros:</div>
        <select data-testid="filter-barber-select" value={filterBarber} onChange={(e) => setFilterBarber(e.target.value)} className="bg-input/60 border border-border rounded-lg px-3 py-2 text-sm outline-none">
          <option value="">Todos barbeiros</option>
          {barbers.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <select data-testid="filter-status-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="bg-input/60 border border-border rounded-lg px-3 py-2 text-sm outline-none">
          <option value="">Todos status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input type="date" data-testid="filter-date-input" value={filterDate} onChange={(e) => setFilterDate(e.target.value)} className="bg-input/60 border border-border rounded-lg px-3 py-2 text-sm outline-none" />
        {filterDate && <button onClick={() => setFilterDate("")} className={btnGhost}>Limpar data</button>}
      </div>

      <div className={card}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="appointments-table">
            <thead>
              <tr className="text-left text-muted-foreground border-b border-border">
                <th className="px-5 py-3 font-semibold">Data / Hora</th>
                <th className="px-5 py-3 font-semibold">Cliente</th>
                <th className="px-5 py-3 font-semibold">Serviço</th>
                <th className="px-5 py-3 font-semibold">Barbeiro</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="px-5 py-10 text-center text-muted-foreground">Nenhum agendamento encontrado.</td></tr>
              )}
              {filtered.map((a) => (
                <tr key={a.id} className="border-b border-border/50 hover:bg-secondary/30" data-testid={`appointment-row-${a.id}`}>
                  <td className="px-5 py-3">
                    <div className="font-semibold">{a.date.split("-").reverse().join("/")}</div>
                    <div className="text-amber-400 font-bold">{a.time}</div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="font-medium">{a.client_name}</div>
                    <div className="text-xs text-muted-foreground">{a.client_phone}</div>
                  </td>
                  <td className="px-5 py-3">{a.service_name}<div className="text-xs text-muted-foreground">R$ {a.price}</div></td>
                  <td className="px-5 py-3">{a.barber_name}</td>
                  <td className="px-5 py-3"><span className={badge(statusColors[a.status])}>{a.status}</span></td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-1">
                      {whatsappUrl(a) && (
                        <a data-testid={`whatsapp-appt-${a.id}`} href={whatsappUrl(a)} target="_blank" rel="noopener noreferrer" title="Enviar lembrete no WhatsApp" className="p-2 rounded-lg text-emerald-400 hover:bg-emerald-500/10"><MessageCircle className="h-4 w-4" /></a>
                      )}
                      {a.status !== "Concluído" && (
                        <button data-testid={`complete-appt-${a.id}`} onClick={() => setStatus(a.id, "Concluído")} title="Concluir" className="p-2 rounded-lg text-emerald-400 hover:bg-emerald-500/10"><CheckCircle2 className="h-4 w-4" /></button>
                      )}
                      {a.status !== "Cancelado" && (
                        <button data-testid={`cancel-appt-${a.id}`} onClick={() => setStatus(a.id, "Cancelado")} title="Cancelar" className="p-2 rounded-lg text-rose-400 hover:bg-rose-500/10"><XCircle className="h-4 w-4" /></button>
                      )}
                      <button data-testid={`delete-appt-${a.id}`} onClick={() => remove(a.id)} title="Excluir" className="p-2 rounded-lg text-muted-foreground hover:bg-secondary"><Trash2 className="h-4 w-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
