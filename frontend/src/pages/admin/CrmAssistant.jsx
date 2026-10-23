import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Sparkles,
  MessageCircle,
  Copy,
  Calendar,
  Gift,
  Clock,
  Crown,
  Search,
  RefreshCw,
  Send,
  SlidersHorizontal,
  BellRing,
  CheckCircle2,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, btnSecondary, card, input, badge } from "@/lib/styles";

export default function CrmAssistant() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("today"); // today | inactive | birthdays | loyalty
  const [search, setSearch] = useState("");

  // Custom modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState(null);
  const [customOffer, setCustomOffer] = useState("");
  const [customMsgText, setCustomMsgText] = useState("");
  const [generating, setGenerating] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.get("/crm-assistant/summary");
      setData(res.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const copyToClipboard = (text) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      toast.success("Mensagem copiada para a área de transferência!");
    } else {
      toast.info("Selecione o texto para copiar.");
    }
  };

  const openWhatsApp = async (url, appointmentId = null) => {
    if (!url) {
      toast.error("Telefone não cadastrado para este cliente.");
      return;
    }
    if (appointmentId) {
      try {
        await api.post(`/crm-assistant/appointments/${appointmentId}/mark-reminded`);
        // Update local state without full reload
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            today_reminders: prev.today_reminders.map((r) =>
              r.appointment_id === appointmentId ? { ...r, reminder_sent: true } : r
            ),
          };
        });
      } catch (e) {
        // Continue even if marking fails
      }
    }
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const openCustomModal = (client, actionType, initialMsg = "") => {
    setSelectedClient({ ...client, actionType });
    setCustomOffer("");
    setCustomMsgText(initialMsg);
    setModalOpen(true);
  };

  const generateCustom = async () => {
    if (!selectedClient) return;
    setGenerating(true);
    try {
      const res = await api.post("/crm-assistant/generate-custom", {
        client_id: selectedClient.client_id,
        action_type: selectedClient.actionType,
        custom_offer: customOffer.trim(),
        custom_text: customMsgText.trim(),
      });
      setCustomMsgText(res.data.message);
      if (res.data.whatsapp_url) {
        setSelectedClient((prev) => ({ ...prev, whatsapp_url: res.data.whatsapp_url }));
      }
      toast.success("Mensagem gerada!");
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setGenerating(false);
    }
  };

  const stats = data?.stats || {
    today_reminders_count: 0,
    inactive_count: 0,
    birthdays_count: 0,
    loyalty_count: 0,
    total_opportunities: 0,
  };

  const todayList = (data?.today_reminders || []).filter((c) =>
    `${c.name} ${c.phone} ${c.barber_name} ${c.time}`.toLowerCase().includes(search.toLowerCase())
  );

  const inactiveList = (data?.inactive_clients || []).filter((c) =>
    `${c.name} ${c.phone} ${c.preferred_barber}`.toLowerCase().includes(search.toLowerCase())
  );

  const birthdayList = (data?.birthday_clients || []).filter((c) =>
    `${c.name} ${c.phone}`.toLowerCase().includes(search.toLowerCase())
  );

  const loyaltyList = (data?.loyalty_clients || []).filter((c) =>
    `${c.name} ${c.phone}`.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="IA & CRM"
        title="Assistente CRM"
        subtitle="Seu copiloto inteligente para zerar faltas (no-show), resgatar clientes sumidos e fidelizar via WhatsApp."
        action={
          <button onClick={loadData} disabled={loading} className={btnSecondary + " flex items-center gap-2"}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Atualizar oportunidades
          </button>
        }
      />

      {/* Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <button
          onClick={() => setActiveTab("today")}
          className={`${card} p-5 text-left transition-all ${
            activeTab === "today" ? "border-amber-500/60 bg-amber-500/5 shadow-md shadow-amber-900/20" : "hover:border-border/80"
          }`}
        >
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs uppercase font-semibold tracking-wider flex items-center gap-1.5 text-amber-400">
              <BellRing className="h-4 w-4" /> Lembretes Hoje (2h)
            </span>
            <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-bold">
              {stats.today_reminders_count}
            </span>
          </div>
          <div className="font-display text-3xl font-extrabold text-foreground">{stats.today_reminders_count}</div>
          <p className="text-xs text-muted-foreground mt-1">Zere faltas com confirmação no WhatsApp.</p>
        </button>

        <button
          onClick={() => setActiveTab("inactive")}
          className={`${card} p-5 text-left transition-all ${
            activeTab === "inactive" ? "border-amber-500/60 bg-amber-500/5 shadow-md shadow-amber-900/20" : "hover:border-border/80"
          }`}
        >
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs uppercase font-semibold tracking-wider flex items-center gap-1.5 text-rose-400">
              <Clock className="h-4 w-4" /> Sumidos (+45 dias)
            </span>
            <span className="text-xs bg-rose-500/10 text-rose-400 px-2 py-0.5 rounded-full font-bold">
              {stats.inactive_count}
            </span>
          </div>
          <div className="font-display text-3xl font-extrabold text-foreground">{stats.inactive_count}</div>
          <p className="text-xs text-muted-foreground mt-1">Clientes prontos para reengajamento.</p>
        </button>

        <button
          onClick={() => setActiveTab("birthdays")}
          className={`${card} p-5 text-left transition-all ${
            activeTab === "birthdays" ? "border-amber-500/60 bg-amber-500/5 shadow-md shadow-amber-900/20" : "hover:border-border/80"
          }`}
        >
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs uppercase font-semibold tracking-wider flex items-center gap-1.5 text-emerald-400">
              <Gift className="h-4 w-4" /> Aniversariantes
            </span>
            <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full font-bold">
              {stats.birthdays_count}
            </span>
          </div>
          <div className="font-display text-3xl font-extrabold text-foreground">{stats.birthdays_count}</div>
          <p className="text-xs text-muted-foreground mt-1">Felicitações e promoções exclusivas.</p>
        </button>

        <button
          onClick={() => setActiveTab("loyalty")}
          className={`${card} p-5 text-left transition-all ${
            activeTab === "loyalty" ? "border-amber-500/60 bg-amber-500/5 shadow-md shadow-amber-900/20" : "hover:border-border/80"
          }`}
        >
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs uppercase font-semibold tracking-wider flex items-center gap-1.5 text-purple-400">
              <Crown className="h-4 w-4" /> Fidelidade & VIP
            </span>
            <span className="text-xs bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-full font-bold">
              {stats.loyalty_count}
            </span>
          </div>
          <div className="font-display text-3xl font-extrabold text-foreground">{stats.loyalty_count}</div>
          <p className="text-xs text-muted-foreground mt-1">Cortes cortesia e metas quase lá.</p>
        </button>
      </div>

      {/* Search & Tabs */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="flex items-center gap-1 bg-secondary/50 p-1 rounded-xl border border-border overflow-x-auto">
          <button
            onClick={() => setActiveTab("today")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
              activeTab === "today" ? "bg-amber-500 text-zinc-950 shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Lembretes Hoje ({stats.today_reminders_count})
          </button>
          <button
            onClick={() => setActiveTab("inactive")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
              activeTab === "inactive" ? "bg-amber-500 text-zinc-950 shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Sumidos (+45d) ({stats.inactive_count})
          </button>
          <button
            onClick={() => setActiveTab("birthdays")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
              activeTab === "birthdays" ? "bg-amber-500 text-zinc-950 shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Aniversariantes ({stats.birthdays_count})
          </button>
          <button
            onClick={() => setActiveTab("loyalty")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
              activeTab === "loyalty" ? "bg-amber-500 text-zinc-950 shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Fidelidade VIP ({stats.loyalty_count})
          </button>
        </div>

        <div className="relative max-w-xs w-full">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por nome ou fone..."
            className={input + " pl-9 text-sm"}
          />
        </div>
      </div>

      {/* Content Area */}
      {loading ? (
        <div className={card + " p-12 text-center text-muted-foreground"}>
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-amber-500" />
          Analisando horários de hoje e oportunidades de CRM...
        </div>
      ) : activeTab === "today" ? (
        <div className="space-y-3">
          {todayList.length === 0 ? (
            <div className={card + " p-10 text-center text-muted-foreground"}>
              Nenhum agendamento confirmado para hoje.
            </div>
          ) : (
            todayList.map((c) => (
              <div
                key={c.appointment_id}
                className={card + " p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-amber-500/30 transition-all"}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className="font-display font-bold text-base text-foreground">{c.name}</span>
                    <span className={badge("bg-amber-500/20 text-amber-300 border-amber-500/30 font-bold")}>
                      Hoje às {c.time}
                    </span>
                    {c.reminder_sent && (
                      <span className={badge("bg-emerald-500/10 text-emerald-400 border-emerald-500/20 flex items-center gap-1")}>
                        <CheckCircle2 className="h-3 w-3" /> Lembrete Enviado
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
                    <span>Telefone: <strong>{c.phone || "—"}</strong></span>
                    <span>Serviço: <strong>{c.service_name}</strong></span>
                    <span>Barbeiro: <strong>{c.barber_name}</strong></span>
                  </div>
                  <div className="rounded-lg bg-secondary/50 border border-border p-2.5 text-xs text-zinc-300 font-mono whitespace-pre-wrap max-w-2xl mt-2">
                    {c.suggested_message}
                  </div>
                </div>

                <div className="flex md:flex-col gap-2 shrink-0">
                  <button
                    onClick={() => openWhatsApp(c.whatsapp_url, c.appointment_id)}
                    className={btnPrimary + " flex items-center justify-center gap-2 text-xs py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white"}
                  >
                    <MessageCircle className="h-4 w-4" /> Enviar Lembrete 2h
                  </button>
                  <button
                    onClick={() => copyToClipboard(c.suggested_message)}
                    className={btnSecondary + " flex items-center justify-center gap-2 text-xs py-2 px-3"}
                  >
                    <Copy className="h-3.5 w-3.5" /> Copiar texto
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : activeTab === "inactive" ? (
        <div className="space-y-3">
          {inactiveList.length === 0 ? (
            <div className={card + " p-10 text-center text-muted-foreground"}>
              Nenhum cliente inativo há mais de 45 dias no momento. Parabéns pelo engajamento da barbearia!
            </div>
          ) : (
            inactiveList.map((c) => (
              <div
                key={c.client_id}
                className={card + " p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-amber-500/30 transition-all"}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className="font-display font-bold text-base text-foreground">{c.name}</span>
                    <span className={badge("bg-rose-500/10 text-rose-400 border-rose-500/20")}>
                      {c.days_inactive} dias sem corte
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
                    <span>Telefone: <strong>{c.phone || "—"}</strong></span>
                    <span>Último corte: <strong>{c.last_visit.split("-").reverse().join("/")}</strong></span>
                    {c.last_service && <span>Serviço: <strong>{c.last_service}</strong></span>}
                    {c.preferred_barber && <span>Barbeiro: <strong>{c.preferred_barber}</strong></span>}
                  </div>
                  <div className="rounded-lg bg-secondary/50 border border-border p-2.5 text-xs text-zinc-300 font-mono whitespace-pre-wrap max-w-2xl mt-2">
                    {c.suggested_message}
                  </div>
                </div>

                <div className="flex md:flex-col gap-2 shrink-0">
                  <button
                    onClick={() => openWhatsApp(c.whatsapp_url)}
                    className={btnPrimary + " flex items-center justify-center gap-2 text-xs py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white"}
                  >
                    <MessageCircle className="h-4 w-4" /> Enviar WhatsApp
                  </button>
                  <button
                    onClick={() => copyToClipboard(c.suggested_message)}
                    className={btnSecondary + " flex items-center justify-center gap-2 text-xs py-2 px-3"}
                  >
                    <Copy className="h-3.5 w-3.5" /> Copiar texto
                  </button>
                  <button
                    onClick={() => openCustomModal(c, "reengage", c.suggested_message)}
                    className="text-[11px] text-amber-400 hover:underline inline-flex items-center justify-center gap-1 mt-1"
                  >
                    <SlidersHorizontal className="h-3 w-3" /> Personalizar oferta
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : activeTab === "birthdays" ? (
        <div className="space-y-3">
          {birthdayList.length === 0 ? (
            <div className={card + " p-10 text-center text-muted-foreground"}>
              Nenhum aniversariante encontrado para hoje ou esta semana. Dica: cadastre a data de aniversário no cadastro de clientes!
            </div>
          ) : (
            birthdayList.map((c) => (
              <div
                key={c.client_id}
                className={card + " p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-emerald-500/30 transition-all"}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className="font-display font-bold text-base text-foreground">{c.name}</span>
                    {c.is_today ? (
                      <span className={badge("bg-emerald-500/20 text-emerald-300 border-emerald-500/40 animate-pulse")}>
                        🎉 Aniversário Hoje!
                      </span>
                    ) : (
                      <span className={badge("bg-emerald-500/10 text-emerald-400 border-emerald-500/20")}>
                        Aniversário: {c.birthdate}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Telefone: <strong>{c.phone || "—"}</strong>
                  </div>
                  <div className="rounded-lg bg-secondary/50 border border-border p-2.5 text-xs text-zinc-300 font-mono whitespace-pre-wrap max-w-2xl mt-2">
                    {c.suggested_message}
                  </div>
                </div>

                <div className="flex md:flex-col gap-2 shrink-0">
                  <button
                    onClick={() => openWhatsApp(c.whatsapp_url)}
                    className={btnPrimary + " flex items-center justify-center gap-2 text-xs py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white"}
                  >
                    <MessageCircle className="h-4 w-4" /> Parabenizar no WhatsApp
                  </button>
                  <button
                    onClick={() => copyToClipboard(c.suggested_message)}
                    className={btnSecondary + " flex items-center justify-center gap-2 text-xs py-2 px-3"}
                  >
                    <Copy className="h-3.5 w-3.5" /> Copiar texto
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {loyaltyList.length === 0 ? (
            <div className={card + " p-10 text-center text-muted-foreground"}>
              Nenhum cliente com 80+ pontos no momento. Conforme os clientes cortarem cabelo, eles pontuarão automaticamente!
            </div>
          ) : (
            loyaltyList.map((c) => (
              <div
                key={c.client_id}
                className={card + " p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-purple-500/30 transition-all"}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className="font-display font-bold text-base text-foreground">{c.name}</span>
                    <span className={badge("bg-purple-500/10 text-purple-400 border-purple-500/20")}>
                      {c.tier} — {c.points} Pontos
                    </span>
                    {c.has_free_cut && (
                      <span className={badge("bg-amber-500/20 text-amber-300 border-amber-500/40 font-bold")}>
                        👑 1 Corte Grátis Liberado
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Telefone: <strong>{c.phone || "—"}</strong>
                  </div>
                  <div className="rounded-lg bg-secondary/50 border border-border p-2.5 text-xs text-zinc-300 font-mono whitespace-pre-wrap max-w-2xl mt-2">
                    {c.suggested_message}
                  </div>
                </div>

                <div className="flex md:flex-col gap-2 shrink-0">
                  <button
                    onClick={() => openWhatsApp(c.whatsapp_url)}
                    className={btnPrimary + " flex items-center justify-center gap-2 text-xs py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white"}
                  >
                    <MessageCircle className="h-4 w-4" /> Avisar no WhatsApp
                  </button>
                  <button
                    onClick={() => copyToClipboard(c.suggested_message)}
                    className={btnSecondary + " flex items-center justify-center gap-2 text-xs py-2 px-3"}
                  >
                    <Copy className="h-3.5 w-3.5" /> Copiar texto
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Modal de Personalização */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-lg bg-card border-border">
          <DialogHeader>
            <DialogTitle className="font-display text-xl flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-amber-400" />
              Personalizar Mensagem — {selectedClient?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Bônus / Oferta Especial (Opcional)
              </label>
              <input
                value={customOffer}
                onChange={(e) => setCustomOffer(e.target.value)}
                placeholder="Ex: 15% de desconto se vier nesta quinta-feira"
                className={input + " mt-1.5 text-sm"}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Texto da Mensagem
              </label>
              <textarea
                rows={6}
                value={customMsgText}
                onChange={(e) => setCustomMsgText(e.target.value)}
                className={input + " mt-1.5 text-xs font-mono"}
              />
            </div>

            <div className="flex items-center justify-between gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={generateCustom}
                disabled={generating}
                className={btnSecondary + " text-xs"}
              >
                <Sparkles className="h-3.5 w-3.5 text-amber-400" /> Regenerar com Oferta
              </button>

              <div className="flex gap-2">
                <button type="button" onClick={() => setModalOpen(false)} className={btnSecondary + " text-xs"}>
                  Fechar
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const text = customMsgText;
                    const phone = selectedClient?.phone;
                    const clean = String(phone || "").replace(/\D/g, "");
                    const finalClean = clean.startsWith("55") ? clean : clean.length >= 10 ? "55" + clean : clean;
                    window.open(`https://wa.me/${finalClean}?text=${encodeURIComponent(text)}`, "_blank");
                  }}
                  className={btnPrimary + " text-xs bg-emerald-600 hover:bg-emerald-500 text-white"}
                >
                  <Send className="h-3.5 w-3.5" /> Disparar WhatsApp
                </button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
