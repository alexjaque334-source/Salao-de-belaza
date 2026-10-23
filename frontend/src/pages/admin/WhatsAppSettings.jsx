import { useEffect, useState } from "react";
import { MessageCircle, CreditCard, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, card, input } from "@/lib/styles";

export default function WhatsAppSettings() {
  const [phone, setPhone] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [plansEnabled, setPlansEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/integrations/whatsapp").then(({ data }) => {
      setPhone(data.phone || "");
      setEnabled(Boolean(data.booking_enabled && data.phone));
      setPlansEnabled(data.plans_enabled !== false);
    }).catch(() => {});
  }, []);

  const save = async () => {
    if (enabled && !phone.trim()) return toast.error("Informe o WhatsApp da barbearia.");
    try {
      setSaving(true);
      await api.put("/integrations/whatsapp", {
        phone: phone.trim(),
        booking_enabled: enabled,
        plans_enabled: plansEnabled,
      });
      toast.success("Configuração salva com sucesso.");
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };

  return <div>
    <PageHeader eyebrow="Configurações" title="WhatsApp & Bio Site" subtitle="Configure a confirmação de agendamentos e a exibição de planos no seu Bio Site público." />
    <div className={card + " max-w-2xl p-6 space-y-6"}>
      <div className="flex items-start gap-3">
        <MessageCircle className="h-6 w-6 text-emerald-400 mt-0.5 shrink-0" />
        <div>
          <div className="font-semibold text-base">WhatsApp da Barbearia</div>
          <p className="text-sm text-muted-foreground mt-1">Usado para receber confirmações imediatas de novos agendamentos e solicitações de planos do Bio Site.</p>
        </div>
      </div>

      <div>
        <label className="text-sm font-medium">Número do WhatsApp (com DDD)</label>
        <input className={input + " mt-1"} value={phone} onChange={e => setPhone(e.target.value)} placeholder="(41) 99999-9999" />
        <p className="text-xs text-muted-foreground mt-2">Não precisa de API oficial da Meta. O cliente clica no link e envia a mensagem pelo próprio WhatsApp dele.</p>
      </div>

      <div className="pt-4 border-t border-border space-y-4">
        <label className="flex items-start gap-3 cursor-pointer">
          <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} className="mt-1 h-4 w-4 rounded border-border" />
          <div>
            <div className="text-sm font-medium">Ativar confirmação de agendamento por WhatsApp</div>
            <div className="text-xs text-muted-foreground">Após agendar no Bio Site, o cliente vê o botão para enviar o resumo direto no WhatsApp da sua barbearia.</div>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <input type="checkbox" checked={plansEnabled} onChange={e => setPlansEnabled(e.target.checked)} className="mt-1 h-4 w-4 rounded border-border" />
          <div>
            <div className="text-sm font-medium flex items-center gap-1.5">
              <span>Exibir botão de Planos Mensais no Bio Site</span>
              <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-full border border-amber-500/20">Clube VIP</span>
            </div>
            <div className="text-xs text-muted-foreground">Quando ativado, os clientes verão o botão de Planos de Assinatura no Bio Site com opção de contratação rápida.</div>
          </div>
        </label>
      </div>

      <button onClick={save} disabled={saving} className={btnPrimary}>{saving ? "Salvando..." : "Salvar configurações"}</button>
    </div>
  </div>;
}
