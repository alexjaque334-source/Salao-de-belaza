import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Scissors, CalendarCheck, Loader2, MessageCircle, Star, Crown,
  Check, Calendar, Clock, User, Phone, Share2, Sparkles, CheckCircle2, ChevronRight, ShieldCheck, MapPin
} from "lucide-react";
import { api, apiError } from "@/lib/api";
import { btnPrimary, btnSecondary, card, input, overline, badge } from "@/lib/styles";
import { toast } from "sonner";

function sendWhatsApp(shop, booked) {
  const cleanPhone = String(shop?.whatsapp?.phone || "").replace(/\D/g, "");
  if (!cleanPhone) {
    toast.error("Número de WhatsApp da barbearia não configurado.");
    return;
  }
  const lines = [
    "Olá! Acabei de fazer um agendamento pelo seu Bio Site da " + shop.name + " 💈",
    "",
    "📋 *Detalhes do Agendamento:*",
    "• *Cliente:* " + booked.client_name,
    "• *Serviço:* " + booked.service_name,
    "• *Profissional:* " + booked.barber_name,
    "• *Data:* " + booked.date.split("-").reverse().join("/"),
    "• *Horário:* " + booked.time,
    "",
    "Tudo certo por aí? Aguardo confirmação! ✂️",
  ];
  const destination = "https://wa.me/" + cleanPhone + "?text=" + encodeURIComponent(lines.join("\n"));
  window.open(destination, "_blank", "noopener,noreferrer");
}

function sendPlanWhatsApp(shop, plan) {
  let cleanPhone = String(shop?.whatsapp?.phone || "").replace(/\D/g, "");
  if (cleanPhone && cleanPhone.length <= 11 && !cleanPhone.startsWith("55")) cleanPhone = "55" + cleanPhone;
  if (!cleanPhone) {
    toast.info("Entre em contato com a barbearia para assinar o plano " + plan.name);
    return;
  }
  const msg = [
    `Olá! Vi o plano *${plan.name}* (R$ ${plan.price}/mês) no Bio Site da ${shop.name} 💈`,
    `Gostaria de saber como funciona para assinar e garantir meus cortes mensais!`,
  ].join("\n");
  const destination = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(msg)}`;
  window.open(destination, "_blank", "noopener,noreferrer");
}

export default function PublicBooking() {
  const { slug } = useParams();
  const [shop, setShop] = useState(null);
  const [shopLoading, setShopLoading] = useState(true);
  const [shopError, setShopError] = useState("");

  const [activeTab, setActiveTab] = useState("booking"); // "booking" | "plans"
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
    const pageTitle = `${shop.name} | Agendamento Online & Planos VIP`;
    const servicesList = (shop.services || []).map((s) => s.name).slice(0, 5).join(", ");
    const pageDesc = `Bio site e agendamento online da ${shop.name}. Serviços: ${servicesList || "Corte, Barba e Combo"}. Escolha profissional, data e horário ou assine nosso plano mensal.`;
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

  const handleShare = async () => {
    try {
      if (navigator.share) {
        await navigator.share({
          title: shop?.name || "Barbearia",
          text: `Agende seu horário na ${shop?.name || "Barbearia"}!`,
          url: window.location.href,
        });
      } else {
        await navigator.clipboard.writeText(window.location.href);
        toast.success("Link do Bio Site copiado para a área de transferência!");
      }
    } catch (_) {}
  };

  const submit = async () => {
    if (!barberId || !serviceId || !time || !name.trim() || !phone.trim()) {
      return toast.error("Por favor, preencha seus dados e escolha serviço, profissional e horário.");
    }
    setLoading(true);
    try {
      const response = await api.post(`/public/shops/${slug}/appointments`, {
        barber_id: barberId,
        service_id: serviceId,
        date,
        time,
        client_name: name.trim(),
        client_phone: phone.trim(),
        website,
      });
      setBooked(response.data.appointment);
      setDone(true);
      toast.success("Horário agendado com sucesso!");
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  };

  const selectedService = shop?.services?.find((s) => s.id === serviceId);
  const selectedBarber = shop?.barbers?.find((b) => b.id === barberId);
  const showPlansTab = Boolean(shop?.show_plans && shop?.plans && shop?.plans.length > 0);

  if (shopLoading) {
    return (
      <div className="relative min-h-screen grid place-items-center bg-zinc-950 text-amber-400 font-sans">
        <div className="flex flex-col items-center gap-3">
          <div className="h-12 w-12 rounded-full border-2 border-amber-500 border-t-transparent animate-spin" />
          <span className="text-sm font-medium tracking-wide text-zinc-300">Carregando bio site da barbearia...</span>
        </div>
      </div>
    );
  }

  if (!shop) {
    return (
      <div className="min-h-screen grid place-items-center bg-zinc-950 text-foreground p-5">
        <div className={card + " w-full max-w-md p-8 text-center border-zinc-800 bg-zinc-900/90 shadow-2xl backdrop-blur-md"}>
          <div className="h-14 w-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 grid place-items-center mx-auto mb-4">
            <Scissors className="h-7 w-7 text-amber-400" />
          </div>
          <h1 className="font-display text-2xl font-bold text-zinc-100">Barbearia indisponível</h1>
          <p role="alert" className="text-sm text-zinc-400 mt-2">
            {shopError || "Não foi possível localizar esta barbearia. Confira o link ou entre em contato com a equipe."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen text-zinc-100 overflow-x-hidden selection:bg-amber-500 selection:text-zinc-950">
      {/* Background Video with Dark Vignette Overlay */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <video
          autoPlay
          loop
          muted
          playsInline
          poster="https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&w=1200&q=80"
          className="absolute inset-0 w-full h-full object-cover scale-105 filter brightness-75 contrast-125 transition-opacity duration-1000"
        >
          <source src="https://assets.mixkit.co/videos/preview/mixkit-barber-cutting-hair-with-scissors-40742-large.mp4" type="video/mp4" />
          <source src="https://assets.mixkit.co/videos/preview/mixkit-barber-shaving-a-client-with-a-razor-40744-large.mp4" type="video/mp4" />
        </video>
        {/* Layered Gradient & Blur to ensure ultra legibility */}
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/85 via-zinc-950/75 to-zinc-950/95 backdrop-blur-[3px]" />
      </div>

      {/* Main Content Container (Bio Site Format) */}
      <div className="relative z-10 max-w-xl mx-auto px-4 py-8 sm:py-12 flex flex-col items-center">
        {/* Bio Profile Card Header */}
        <div className="w-full flex flex-col items-center text-center mb-6">
          <div className="relative group">
            <div className="absolute -inset-1 rounded-full bg-gradient-to-r from-amber-500 to-amber-300 opacity-75 blur group-hover:opacity-100 transition duration-500" />
            <div className="relative h-24 w-24 rounded-full bg-zinc-900 border-2 border-amber-400/80 flex items-center justify-center shadow-2xl overflow-hidden">
              <Scissors className="h-10 w-10 text-amber-400 rotate-[-45deg]" />
            </div>
            <div className="absolute bottom-0 right-0 bg-emerald-500 text-zinc-950 p-1 rounded-full border-2 border-zinc-950 shadow-md" title="Atendimento Online">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </div>

          <div className="mt-4 flex items-center justify-center gap-1.5">
            <h1 className="font-display text-2xl sm:text-3xl font-black text-white tracking-tight">{shop.name}</h1>
            <ShieldCheck className="h-5 w-5 text-amber-400 shrink-0" title="Perfil Oficial Verificado" />
          </div>

          <p className="text-xs sm:text-sm text-zinc-300 mt-1 max-w-xs font-medium">
            Agendamento online 24h • Estilo clássico & contemporâneo
          </p>

          {/* Bio Quick Actions */}
          <div className="flex items-center gap-2 mt-4">
            {shop.whatsapp?.phone && (
              <a
                href={`https://wa.me/${String(shop.whatsapp.phone).replace(/\D/g, "")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold hover:bg-emerald-500/20 transition-all"
              >
                <MessageCircle className="h-3.5 w-3.5" /> Falar no WhatsApp
              </a>
            )}
            <button
              onClick={handleShare}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-800/80 border border-zinc-700/80 text-zinc-300 text-xs font-semibold hover:bg-zinc-700 transition-all"
            >
              <Share2 className="h-3.5 w-3.5" /> Compartilhar
            </button>
          </div>
        </div>

        {/* Bio Navigation Selector (Agendamento vs Planos Mensais) */}
        {showPlansTab && (
          <div className="w-full bg-zinc-900/80 border border-zinc-800 p-1.5 rounded-2xl backdrop-blur-md shadow-lg flex gap-1 mb-6">
            <button
              type="button"
              onClick={() => setActiveTab("booking")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                activeTab === "booking"
                  ? "bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/20"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
              }`}
            >
              <Calendar className="h-4 w-4" />
              Agendar Horário
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("plans")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                activeTab === "plans"
                  ? "bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/20"
                  : "text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
              }`}
            >
              <Crown className="h-4 w-4" />
              Planos & Clube VIP
              <span className="text-[10px] bg-amber-400 text-zinc-950 font-black px-1.5 py-0.2 rounded-full uppercase ml-1 animate-pulse">
                VIP
              </span>
            </button>
          </div>
        )}

        {/* TAB 1: BOOKING WIZARD */}
        {activeTab === "booking" && (
          <div className="w-full">
            {done ? (
              <div className="rounded-3xl border border-zinc-800 bg-zinc-900/90 p-6 sm:p-8 text-center backdrop-blur-xl shadow-2xl animate-in fade-in zoom-in-95 duration-300">
                <div className="h-16 w-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                  <CalendarCheck className="h-8 w-8 text-emerald-400" />
                </div>
                <h2 className="font-display text-2xl font-black text-white">Agendamento Confirmado!</h2>
                <p className="text-zinc-400 text-sm mt-2">
                  Seu horário foi reservado com sucesso na agenda da {shop.name}.
                </p>

                {booked && (
                  <div className="mt-6 rounded-2xl bg-zinc-950/70 border border-zinc-800 p-5 text-left space-y-2 text-sm">
                    <div className="flex justify-between border-b border-zinc-800 pb-2">
                      <span className="text-zinc-400">Serviço:</span>
                      <span className="font-bold text-amber-400">{booked.service_name}</span>
                    </div>
                    <div className="flex justify-between border-b border-zinc-800 pb-2">
                      <span className="text-zinc-400">Profissional:</span>
                      <span className="font-medium text-white">{booked.barber_name}</span>
                    </div>
                    <div className="flex justify-between border-b border-zinc-800 pb-2">
                      <span className="text-zinc-400">Data:</span>
                      <span className="font-medium text-white">{booked.date.split("-").reverse().join("/")}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Horário:</span>
                      <span className="font-bold text-emerald-400 text-base">{booked.time}</span>
                    </div>
                  </div>
                )}

                {shop.whatsapp?.booking_enabled && shop.whatsapp?.phone && booked && (
                  <button
                    type="button"
                    onClick={() => sendWhatsApp(shop, booked)}
                    className="mt-6 w-full flex items-center justify-center gap-2 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold py-3.5 px-4 shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98]"
                  >
                    <MessageCircle className="h-5 w-5" /> Enviar confirmação no WhatsApp
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    setDone(false);
                    setBooked(null);
                    setTime("");
                  }}
                  className="mt-4 text-xs font-semibold text-zinc-400 hover:text-amber-400 transition-colors"
                >
                  Fazer outro agendamento
                </button>
              </div>
            ) : (
              <div className="rounded-3xl border border-zinc-800/90 bg-zinc-900/90 p-5 sm:p-7 backdrop-blur-xl shadow-2xl space-y-6">
                {/* 1. Escolha do Serviço */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-amber-400 mb-2.5">
                    1. Escolha o Serviço
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {shop.services.map((s) => {
                      const isSelected = serviceId === s.id;
                      return (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => setServiceId(s.id)}
                          className={`text-left p-3.5 rounded-2xl border transition-all flex flex-col justify-between ${
                            isSelected
                              ? "border-amber-500 bg-amber-500/10 shadow-md shadow-amber-500/10 ring-1 ring-amber-500"
                              : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700 hover:bg-zinc-800/40"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className={`text-sm font-bold ${isSelected ? "text-amber-400" : "text-white"}`}>
                              {s.name}
                            </span>
                            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
                              {s.duration} min
                            </span>
                          </div>
                          <div className="text-sm font-extrabold text-amber-400/90 mt-2">
                            R$ {Number(s.price).toFixed(2).replace(".", ",")}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 2. Escolha do Barbeiro */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-amber-400 mb-2.5">
                    2. Escolha o Profissional
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {shop.barbers.map((b) => {
                      const isSelected = barberId === b.id;
                      return (
                        <button
                          key={b.id}
                          type="button"
                          onClick={() => setBarberId(b.id)}
                          className={`p-3 rounded-2xl border text-center transition-all flex flex-col items-center gap-1.5 ${
                            isSelected
                              ? "border-amber-500 bg-amber-500/10 ring-1 ring-amber-500 shadow-md shadow-amber-500/10"
                              : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700 hover:bg-zinc-800/40"
                          }`}
                        >
                          <div className="h-10 w-10 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-amber-400 font-bold text-sm">
                            {b.name.slice(0, 2).toUpperCase()}
                          </div>
                          <span className={`text-xs font-bold truncate max-w-full ${isSelected ? "text-amber-400" : "text-white"}`}>
                            {b.name}
                          </span>
                          {b.specialty && (
                            <span className="text-[10px] text-zinc-400 truncate max-w-full">
                              {b.specialty}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 3. Data */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-amber-400 mb-2.5">
                    3. Escolha a Data
                  </label>
                  <div className="relative">
                    <input
                      type="date"
                      min={new Date().toISOString().slice(0, 10)}
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      className={input + " bg-zinc-950/80 border-zinc-800 text-white font-medium"}
                    />
                  </div>
                </div>

                {/* 4. Grade de Horários */}
                {barberId && serviceId && (
                  <div>
                    <div className="flex items-center justify-between mb-2.5">
                      <label className="text-xs font-bold uppercase tracking-wider text-amber-400">
                        4. Horários Disponíveis
                      </label>
                      {time && (
                        <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                          Selecionado: {time}
                        </span>
                      )}
                    </div>

                    {slotsLoading ? (
                      <div className="py-6 flex items-center justify-center gap-2 text-xs text-zinc-400">
                        <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
                        Verificando disponibilidade em tempo real...
                      </div>
                    ) : slotsError ? (
                      <p className="text-xs text-rose-400 py-3">{slotsError}</p>
                    ) : slots.length === 0 ? (
                      <div className="p-4 rounded-2xl bg-zinc-950/50 border border-zinc-800/80 text-center text-xs text-zinc-400">
                        Nenhum horário livre com {selectedBarber?.name} nesta data. Tente outra data ou profissional.
                      </div>
                    ) : (
                      <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                        {slots.map((s) => (
                          <button
                            type="button"
                            key={s.time}
                            disabled={!s.available || loading}
                            onClick={() => setTime(s.time)}
                            className={`py-2 px-1 rounded-xl text-xs font-bold border transition-all ${
                              !s.available
                                ? "opacity-25 border-zinc-900 bg-zinc-950/30 line-through cursor-not-allowed"
                                : time === s.time
                                ? "border-amber-500 bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/20 scale-[1.03]"
                                : "border-zinc-800 bg-zinc-950/60 text-zinc-300 hover:border-amber-500/50 hover:text-white"
                            }`}
                          >
                            {s.time}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* 5. Dados do Cliente */}
                <div className="pt-2 border-t border-zinc-800/80 space-y-3">
                  <label className="block text-xs font-bold uppercase tracking-wider text-amber-400">
                    5. Seus Dados de Contato
                  </label>
                  <div className="grid sm:grid-cols-2 gap-3">
                    <div>
                      <input
                        maxLength={120}
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className={input + " bg-zinc-950/80 border-zinc-800 text-white text-sm"}
                        placeholder="Seu nome completo"
                      />
                    </div>
                    <div>
                      <input
                        maxLength={30}
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        className={input + " bg-zinc-950/80 border-zinc-800 text-white text-sm"}
                        placeholder="WhatsApp com DDD: (41) 99999-9999"
                      />
                    </div>
                  </div>
                </div>

                {/* Honeypot field (anti-spam) */}
                <div aria-hidden="true" className="hidden">
                  <label>
                    Website
                    <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
                  </label>
                </div>

                {/* Submit Button */}
                <button
                  type="button"
                  onClick={submit}
                  disabled={loading || !time || !serviceId || !barberId}
                  className="w-full flex items-center justify-center gap-2 py-4 px-6 rounded-2xl bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-950 font-extrabold text-sm sm:text-base tracking-wide shadow-xl shadow-amber-500/25 transition-all active:scale-[0.99]"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" /> Confirmando...
                    </>
                  ) : (
                    <>
                      <CalendarCheck className="h-5 w-5" /> Confirmar Agendamento
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: VIP MONTHLY PLANS */}
        {activeTab === "plans" && showPlansTab && (
          <div className="w-full space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="text-center mb-4">
              <h2 className="font-display text-xl sm:text-2xl font-bold text-white flex items-center justify-center gap-2">
                <Crown className="h-5 w-5 text-amber-400" /> Planos de Assinatura Mensal
              </h2>
              <p className="text-xs sm:text-sm text-zinc-300 mt-1">
                Cortes garantidos todo mês com economia e benefícios exclusivos da {shop.name}.
              </p>
            </div>

            <div className="grid gap-4">
              {shop.plans.map((p) => (
                <div
                  key={p.id}
                  className={`relative rounded-3xl border p-5 sm:p-6 backdrop-blur-xl transition-all shadow-xl ${
                    p.recommended
                      ? "border-amber-500/80 bg-gradient-to-b from-amber-500/10 via-zinc-900/90 to-zinc-900/95 ring-1 ring-amber-500/50"
                      : "border-zinc-800 bg-zinc-900/90"
                  }`}
                >
                  {p.recommended && (
                    <div className="absolute -top-3 left-6">
                      <span className="inline-flex items-center gap-1 bg-amber-500 text-zinc-950 text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-full shadow-md">
                        <Star className="h-3 w-3 fill-current" /> Recomendado
                      </span>
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-1">
                    <div>
                      <h3 className="font-display text-xl font-black text-white">{p.name}</h3>
                      {p.description && (
                        <p className="text-xs text-zinc-400 mt-1 max-w-sm">{p.description}</p>
                      )}
                    </div>

                    <div className="flex items-baseline gap-1 text-left sm:text-right">
                      <span className="font-display text-3xl font-black text-amber-400">
                        R$ {Number(p.price || 0).toLocaleString("pt-BR")}
                      </span>
                      <span className="text-xs text-zinc-400 font-medium">/mês</span>
                    </div>
                  </div>

                  {p.cuts_per_month && (
                    <div className="mt-3 inline-block px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-bold">
                      ✂️ {p.cuts_per_month}
                    </div>
                  )}

                  {Array.isArray(p.features) && p.features.length > 0 && (
                    <ul className="mt-4 space-y-2 border-t border-zinc-800/80 pt-4">
                      {p.features.map((feat, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs text-zinc-300">
                          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                          <span>{feat}</span>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="mt-5">
                    <button
                      type="button"
                      onClick={() => sendPlanWhatsApp(shop, p)}
                      className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                        p.recommended
                          ? "bg-amber-500 hover:bg-amber-400 text-zinc-950 shadow-md shadow-amber-500/20"
                          : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20"
                      }`}
                    >
                      <MessageCircle className="h-4 w-4" /> Quero assinar via WhatsApp
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => setActiveTab("booking")}
                className="text-xs text-amber-400 hover:underline font-semibold"
              >
                ← Voltar para agendamento avulso
              </button>
            </div>
          </div>
        )}

        {/* Bio Site Footer Brand */}
        <div className="mt-10 text-center">
          <p className="text-[11px] text-zinc-500">
            Powered by <strong className="text-zinc-400">BarberStudio</strong> • Plataforma SaaS para Barbearias
          </p>
        </div>
      </div>
    </div>
  );
}
