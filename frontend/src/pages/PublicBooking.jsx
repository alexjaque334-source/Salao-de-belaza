import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Scissors, CalendarCheck, Loader2, MessageCircle } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { btnPrimary, card, input, overline } from "@/lib/styles";
import { toast } from "sonner";

export default function PublicBooking() {
  const { slug } = useParams();
  const [shop, setShop] = useState(null);
  const [barberId, setBarberId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [slots, setSlots] = useState([]);
  const [time, setTime] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [booked, setBooked] = useState(null);

  useEffect(() => {
    api.get(`/public/shops/${slug}`).then((r) => setShop(r.data)).catch((e) => toast.error(apiError(e)));
  }, [slug]);

  useEffect(() => {
    if (!barberId || !date) return setSlots([]);
    setTime("");
    api.get(`/public/shops/${slug}/availability?barber_id=${barberId}&date=${date}`)
      .then((r) => setSlots(r.data.slots)).catch(() => setSlots([]));
  }, [slug, barberId, date]);

  const submit = async () => {
    if (!barberId || !serviceId || !time || !name.trim() || !phone.trim()) return toast.error("Preencha seus dados e escolha serviço, barbeiro e horário.");
    setLoading(true);
    try {
      const response = await api.post(`/public/shops/${slug}/appointments`, {
        barber_id: barberId, service_id: serviceId, date, time,
        client_name: name.trim(), client_phone: phone.trim(),
      });
      setBooked(response.data.appointment);
      setDone(true);
    } catch (e) { toast.error(apiError(e)); }
    finally { setLoading(false); }
  };

  if (!shop) return <div className="min-h-screen grid place-items-center bg-background text-muted-foreground">Carregando barbearia...</div>;

  return <div className="min-h-screen bg-background text-foreground p-5 sm:p-10">
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <div className="h-11 w-11 rounded-xl bg-amber-500 grid place-items-center"><Scissors className="h-5 w-5 text-zinc-950" /></div>
        <div><div className={overline}>Agendamento online</div><h1 className="font-display text-2xl font-extrabold">{shop.name}</h1></div>
      </div>
      {done ? <div className={card + " p-8 text-center"}>
        <CalendarCheck className="h-12 w-12 text-emerald-400 mx-auto mb-3" />
        <h2 className="font-display text-2xl font-bold">Agendamento confirmado!</h2>
        <p className="text-muted-foreground mt-2">Seu horário foi enviado diretamente para a agenda da {shop.name}.</p>
      </div> : <div className={card + " p-6 space-y-5"}>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><label className="text-sm font-medium">Serviço</label><select value={serviceId} onChange={(e)=>setServiceId(e.target.value)} className={input+" mt-1"}><option value="">Selecione...</option>{shop.services.map(s=><option key={s.id} value={s.id}>{s.name} — R$ {Number(s.price).toFixed(2).replace(".",",")}</option>)}</select></div>
          <div><label className="text-sm font-medium">Profissional</label><select value={barberId} onChange={(e)=>setBarberId(e.target.value)} className={input+" mt-1"}><option value="">Selecione...</option>{shop.barbers.map(b=><option key={b.id} value={b.id}>{b.name}{b.specialty ? ` — ${b.specialty}` : ""}</option>)}</select></div>
          <div><label className="text-sm font-medium">Data</label><input type="date" min={new Date().toISOString().slice(0,10)} value={date} onChange={(e)=>setDate(e.target.value)} className={input+" mt-1"} /></div>
        </div>
        {barberId && <div><div className="text-sm font-medium mb-2">Horário</div><div className="grid grid-cols-3 sm:grid-cols-6 gap-2">{slots.map(s=><button type="button" key={s.time} disabled={!s.available} onClick={()=>setTime(s.time)} className={`py-2 rounded-lg border text-sm ${!s.available ? "opacity-30 line-through" : time===s.time ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-border"}`}>{s.time}</button>)}</div></div>}
        <div className="grid sm:grid-cols-2 gap-4">
          <div><label className="text-sm font-medium">Seu nome</label><input value={name} onChange={(e)=>setName(e.target.value)} className={input+" mt-1"} placeholder="Nome completo" /></div>
          <div><label className="text-sm font-medium">Telefone / WhatsApp</label><input value={phone} onChange={(e)=>setPhone(e.target.value)} className={input+" mt-1"} placeholder="(41) 99999-9999" /></div>
        </div>
        <button onClick={submit} disabled={loading || !time} className={btnPrimary+" w-full"}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck className="h-4 w-4" />} Confirmar agendamento</button>
      </div>}
    </div>
  </div>;
}
