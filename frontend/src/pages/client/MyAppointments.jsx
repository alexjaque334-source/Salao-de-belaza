import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarX, Clock } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { card, badge, statusColors, btnSecondary } from "@/lib/styles";

export default function MyAppointments() {
  const [appts, setAppts] = useState([]);

  const load = () => api.get("/appointments").then((r) => setAppts(r.data));
  useEffect(() => { load(); }, []);

  const cancel = async (id) => {
    try { await api.delete(`/appointments/${id}`); toast.success("Agendamento cancelado"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const sorted = [...appts].sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time));

  return (
    <div>
      <PageHeader eyebrow="Histórico" title="Meus Agendamentos" subtitle="Acompanhe seus horários marcados." />
      {sorted.length === 0 ? (
        <div className={card + " p-12 text-center"}>
          <CalendarX className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <div className="text-muted-foreground">Você ainda não tem agendamentos.</div>
        </div>
      ) : (
        <div className="space-y-3" data-testid="my-appointments-list">
          {sorted.map((a) => (
            <div key={a.id} className={card + " p-5 flex flex-wrap items-center justify-between gap-4"} data-testid={`my-appt-${a.id}`}>
              <div className="flex items-center gap-5">
                <div className="text-center min-w-[64px]">
                  <div className="font-display text-xl font-extrabold text-amber-400">{a.time}</div>
                  <div className="text-xs text-muted-foreground">{a.date.split("-").reverse().join("/")}</div>
                </div>
                <div>
                  <div className="font-semibold">{a.service_name}</div>
                  <div className="text-sm text-muted-foreground">com {a.barber_name} • R$ {a.price}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={badge(statusColors[a.status])}>{a.status}</span>
                {a.status === "Confirmado" && (
                  <button data-testid={`cancel-my-appt-${a.id}`} onClick={() => cancel(a.id)} className={btnSecondary}>Cancelar</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
