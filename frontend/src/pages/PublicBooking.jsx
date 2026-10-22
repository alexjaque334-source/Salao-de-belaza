import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Scissors, CalendarCheck, Loader2, MessageCircle } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { btnPrimary, card, input, overline } from "@/lib/styles";
import { toast } from "sonner";

function sendWhatsApp(shop, booked) {
  const cleanPhone = String(shop?.whatsapp?.phone || "").replace(/\D/g, "");
  if (!cleanPhone) {
    toast.error("Número de WhatsApp da barbearia inválido.");
    return;
  }
  const lines = [
    "Olá! Acabei de fazer um agendamento na " + shop.name + ".",
    "Cliente: " + booked.client_name,
    "Serviço: " + booked.service_name,
    "Profissional: " + booked.barber_name,
    "Data: " + booked.date.split("-").reverse().join("/"),
    "Horário: " + booked.time,
  ];
  const destination = "https://wa.me/" + cleanPhone + "?text=" + encodeURIComponent(lines.join("\n"));
  window.open(destination, "_blank", "noopener,noreferrer");
}

export default function PublicBooking() {
  const { slug } = useParams();
  const [shop, setShop] = useState(null);
  const [shopLoading, setShopLoading] = useState(true);
  const [shopError, setShopError] = useState("");
  const [barberId, setBarberId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState("");
  const [time, setTime] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [booked, setBooked] = useState(null);

  useEffect(() => {
    if (!shop?.name) return;
    const pageTitle = `Agendar Horário em ${shop.name} | BarberStudio`;
    const servicesList = (shop.services || []).map((s) => s.name).slice(0, 5).join(", ");
    const pageDesc = `Agende online seu horário na ${shop.name}. Serviços: ${servicesList || "Corte, Barba e Combo"}. Escolha profissional, data e horário em segundos.`;
    document.title = pageTitle;

    const setMeta = (selector, attr, val) => {
      let el = document.querySelector(selector);
      if (el) el.setAttribute(attr, val);
    };
    setMeta('meta[name="description"]', "content", pageDesc);
    setMeta('meta[property="og:title"]', "content", pageTitle);
    setMeta('meta[property="og:description"]', "content", pageDesc);
    setMeta('meta[name="twitter:title"]', "content", pageTitle);
    setMeta('meta[name="twitter:description"]', "content", pageDesc);

    const schemaId = "barbershop-jsonld-schema";
    let scriptEl = document.getElementById(schemaId);
    if (!scriptEl) {
      scriptEl = document.createElement("script");
      scriptEl.id = schemaId;
      scriptEl.type = "application/ld+json";
      document.head.appendChild(scriptEl);
    }
    const schemaData = {
      "@context": "https://schema.org",
      "@type": "Barbershop",
      name: shop.name,
      url: window.location.href,
      description: pageDesc,
      priceRange: "$$",
      ...(shop.whatsapp?.phone ? { telephone: `+${String(shop.whatsapp.phone).replace(/\D/g, "")}` } : {}),
      hasOfferCatalog: {
        "@type": "OfferCatalog",
        name: "Serviços de Barbearia",
        itemListElement: (shop.services || []).map((s) => ({
          "@type": "Offer",
          itemOffered: {
            "@type": "Service",
            name: s.name,
          },
          price: Number(s.price || 0).toFixed(2),
          priceCurrency: "BRL",
        })),
      },
    };
    scriptEl.textContent = JSON.stringify(schemaData);
  }, [shop]);

  useEffect(() => {
    let active = true;
    setShopLoading(true);
    setShopError("");
    setShop(null);
    api.get(`/public/shops/${slug}`)
      .then((r) => {
        const data = r.data;
        if (!data || typeof data.name !== "string" || !Array.isArray(data.barbers) || !Array.isArray(data.services)) {
          throw new Error("A resposta do agendamento público está inválida. Verifique a configuração da API.");
        }
        if (active) setShop(data);
      })
      .catch((e) => { if (active) setShopError(apiError(e)); })
      .finally(() => { if (active) setShopLoading(false); });
    return () => { active = false; };
  }, [slug]);

  useEffect(() => {
    let active = true;
    if (!barberId || !serviceId || !date) {
      setSlots([]);
      setSlotsError("");
      setSlotsLoading(false);
      setTime("");
      return () => { active = false; };
    }
    setTime("");
    setSlotsError("");
    setSlotsLoading(true);
    api.get(`/public/shops/${slug}/availability?barber_id=${barberId}&date=${date}&service_id=${serviceId}`)
      .then((r) => {
        if (!Array.isArray(r.data?.slots)) {
          throw new Error("Não foi possível ler os horários disponíveis.");
        }
        if (active) setSlots(r.data.slots);
      })
      .catch((e) => {
        if (active) {
          setSlots([]);
          setSlotsError(apiError(e));
        }
      })
      .finally(() => { if (active) setSlotsLoading(false); });
    return () => { active = false; };
  }, [slug, barberId, serviceId, date]);

  const submit = async () => {
    if (!barberId || !serviceId || !time || !name.trim() || !phone.trim()) return toast.error("Preencha seus dados e escolha serviço, barbeiro e horário.");
    setLoading(true);
    try {
      const response = await api.post(`/public/shops/${slug}/appointments`, {
        barber_id: barberId, service_id: serviceId, date, time,
        client_name: name.trim(), client_phone: phone.trim(), website,
      });
      setBooked(response.data.appointment);
      setDone(true);
    } catch (e) { toast.error(apiError(e)); }
    finally { setLoading(false); }
  };

  if (shopLoading) return <div className="min-h-screen grid place-items-center bg-background text-muted-foreground">Carregando barbearia...</div>;
  if (!shop) return <div className="min-h-screen grid place-items-center bg-background text-foreground p-5">
    <div className={card + " w-full max-w-md p-6 text-center"}>
      <Scissors className="h-9 w-9 text-amber-400 mx-auto mb-3" />
      <h1 className="font-display text-xl font-bold">Agendamento indisponível</h1>
      <p role="alert" className="text-sm text-muted-foreground mt-2">{shopError || "Não foi possível localizar esta barbearia. Confira o link ou fale diretamente com a equipe."}</p>
    </div>
  </div>;

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
        {booked && <div className="mt-5 rounded-xl border border-border p-4 text-left text-sm"><div><strong>Serviço:</strong> {booked.service_name}</div><div><strong>Profissional:</strong> {booked.barber_name}</div><div><strong>Data:</strong> {booked.date.split("-").reverse().join("/")}</div><div><strong>Horário:</strong> {booked.time}</div></div>}
        {shop.whatsapp?.booking_enabled && shop.whatsapp?.phone && booked && <button type="button" onClick={() => sendWhatsApp(shop, booked)} className={btnPrimary + " mt-5 w-full"}><MessageCircle className="h-4 w-4" /> Enviar confirmação para a barbearia</button>}
      </div> : <div className={card + " p-6 space-y-5"}>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><label className="text-sm font-medium">Serviço</label><select value={serviceId} onChange={(e)=>setServiceId(e.target.value)} className={input+" mt-1"}><option value="">Selecione...</option>{shop.services.map(s=><option key={s.id} value={s.id}>{s.name} — R$ {Number(s.price).toFixed(2).replace(".",",")}</option>)}</select></div>
          <div><label className="text-sm font-medium">Profissional</label><select value={barberId} onChange={(e)=>setBarberId(e.target.value)} className={input+" mt-1"}><option value="">Selecione...</option>{shop.barbers.map(b=><option key={b.id} value={b.id}>{b.name}{b.specialty ? ` — ${b.specialty}` : ""}</option>)}</select></div>
          <div><label className="text-sm font-medium">Data</label><input type="date" min={new Date().toISOString().slice(0,10)} value={date} onChange={(e)=>setDate(e.target.value)} className={input+" mt-1"} /></div>
        </div>
        {barberId && serviceId && <div>
          <div className="text-sm font-medium mb-2">Horário</div>
          {slotsLoading ? <p className="text-sm text-muted-foreground" role="status">Buscando horários disponíveis...</p>
            : slotsError ? <p className="text-sm text-rose-400" role="alert">{slotsError}</p>
            : slots.length === 0 ? <p className="text-sm text-muted-foreground" role="status">Não há horários disponíveis nesta data. Escolha outra data ou profissional.</p>
            : <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">{slots.map(s=><button type="button" key={s.time} disabled={!s.available || loading} onClick={()=>setTime(s.time)} className={`py-2 rounded-lg border text-sm ${!s.available ? "opacity-30 line-through" : time===s.time ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-border"}`}>{s.time}</button>)}</div>}
        </div>}
        <div className="grid sm:grid-cols-2 gap-4">
          <div><label className="text-sm font-medium">Seu nome</label><input maxLength={120} value={name} onChange={(e)=>setName(e.target.value)} className={input+" mt-1"} placeholder="Nome completo" /></div>
          <div><label className="text-sm font-medium">Telefone / WhatsApp</label><input maxLength={30} value={phone} onChange={(e)=>setPhone(e.target.value)} className={input+" mt-1"} placeholder="(41) 99999-9999" /></div>
        </div>
        <div aria-hidden="true" className="hidden">
          <label>Website<input tabIndex={-1} autoComplete="off" value={website} onChange={(e)=>setWebsite(e.target.value)} /></label>
        </div>
        <button onClick={submit} disabled={loading || !time} className={btnPrimary+" w-full"}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck className="h-4 w-4" />} Confirmar agendamento</button>
      </div>}
    </div>
  </div>;
}
