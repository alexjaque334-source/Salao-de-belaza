import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Loader2, CalendarCheck } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { btnPrimary, btnSecondary, card } from "@/lib/styles";

export function BookingWizard({ isAdmin = false, onBooked }) {
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [clients, setClients] = useState([]);
  const [barberId, setBarberId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [clientId, setClientId] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [slots, setSlots] = useState([]);
  const [time, setTime] = useState("");
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get("/barbers").then((r) => setBarbers(r.data.filter((b) => b.active)));
    api.get("/services").then((r) => setServices(r.data));
    if (isAdmin) api.get("/clients").then((r) => setClients(r.data)).catch(() => {});
  }, [isAdmin]);

  useEffect(() => {
    if (!barberId || !date) {
      setSlots([]);
      return;
    }
    setLoadingSlots(true);
    setTime("");
    api
      .get(`/availability?barber_id=${barberId}&date=${date}`)
      .then((r) => setSlots(r.data.slots))
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false));
  }, [barberId, date]);

  const submit = async () => {
    if (!barberId || !serviceId || !time) {
      toast.error("Selecione barbeiro, serviço e horário.");
      return;
    }
    if (isAdmin && !clientId) {
      toast.error("Selecione o cliente.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/appointments", {
        barber_id: barberId,
        service_id: serviceId,
        date,
        time,
        client_id: isAdmin ? clientId : undefined,
      });
      toast.success(`Agendamento confirmado para ${date.split("-").reverse().join("/")} às ${time}!`);
      setTime("");
      const r = await api.get(`/availability?barber_id=${barberId}&date=${date}`);
      setSlots(r.data.slots);
      onBooked && onBooked();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const selBarber = barbers.find((b) => b.id === barberId);

  return (
    <div className="space-y-6">
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="text-sm font-medium block mb-1.5">Barbeiro</label>
          <select data-testid="booking-barber-select" value={barberId} onChange={(e) => setBarberId(e.target.value)}
            className="w-full bg-input/60 border border-border rounded-xl px-3 py-2.5 text-sm outline-none focus:border-amber-500">
            <option value="">Selecione...</option>
            {barbers.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm font-medium block mb-1.5">Serviço</label>
          <select data-testid="booking-service-select" value={serviceId} onChange={(e) => setServiceId(e.target.value)}
            className="w-full bg-input/60 border border-border rounded-xl px-3 py-2.5 text-sm outline-none focus:border-amber-500">
            <option value="">Selecione...</option>
            {services.map((s) => <option key={s.id} value={s.id}>{s.name} — R$ {s.price}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm font-medium block mb-1.5">Data</label>
          <input data-testid="booking-date-picker" type="date" value={date} min={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
            className="w-full bg-input/60 border border-border rounded-xl px-3 py-2.5 text-sm outline-none focus:border-amber-500" />
        </div>
        {isAdmin && (
          <div>
            <label className="text-sm font-medium block mb-1.5">Cliente</label>
            <select data-testid="booking-client-select" value={clientId} onChange={(e) => setClientId(e.target.value)}
              className="w-full bg-input/60 border border-border rounded-xl px-3 py-2.5 text-sm outline-none focus:border-amber-500">
              <option value="">Selecione...</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        )}
      </div>

      {selBarber && (
        <div className={card + " p-5"}>
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">Horários disponíveis — {selBarber.name}</div>
            {loadingSlots && <Loader2 className="h-4 w-4 animate-spin text-amber-500" />}
          </div>
          {!loadingSlots && slots.length === 0 && (
            <div className="text-sm text-muted-foreground py-6 text-center">
              Este barbeiro não atende nesta data. Escolha outro dia.
            </div>
          )}
          <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-6 gap-2">
            {slots.map((s) => (
              <button
                key={s.time}
                data-testid={`booking-time-slot-${s.time.replace(":", "-")}`}
                disabled={!s.available}
                onClick={() => setTime(s.time)}
                className={`py-2.5 rounded-xl text-sm font-semibold border transition-all ${
                  !s.available
                    ? "bg-secondary/40 text-muted-foreground/40 border-border line-through cursor-not-allowed"
                    : time === s.time
                    ? "bg-gradient-to-r from-amber-600 to-amber-500 text-zinc-950 border-amber-400"
                    : "bg-secondary text-foreground border-border hover:border-amber-500/60"
                }`}
              >
                {s.time}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button data-testid="booking-submit-button" onClick={submit} disabled={submitting || !time} className={btnPrimary}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck className="h-4 w-4" />}
          Confirmar Agendamento
        </button>
      </div>
    </div>
  );
}
