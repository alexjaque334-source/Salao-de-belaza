import { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, card, input } from "@/lib/styles";

export default function WhatsAppSettings() {
  const [phone, setPhone] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/integrations/whatsapp").then(({ data }) => {
      setPhone(data.phone || "");
      setEnabled(Boolean(data.booking_enabled && data.phone));
    }).catch(() => {});
  }, []);

  const save = async () => {
    if (enabled && !phone.trim()) return toast.error("Informe o WhatsApp da barbearia.");
    try {
      setSaving(true);
      await api.put("/integrations/whatsapp", { phone: phone.trim(), booking_enabled: enabled, plans_enabled: false });
      toast.success("Configuração do WhatsApp salva.");
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };

  return <div>
    <PageHeader eyebrow="Configurações" title="WhatsApp" subtitle="Configure a confirmação dos agendamentos feitos pelo link público." />
    <div className={card + " max-w-2xl p-6 space-y-5"}>
      <div className="flex items-start gap-3">
        <MessageCircle className="h-6 w-6 text-emerald-400 mt-0.5" />
        <div><div className="font-semibold">Receber confirmações pelo WhatsApp</div><p className="text-sm text-muted-foreground mt-1">Quando ativado, após o agendamento o cliente poderá abrir o WhatsApp com a confirmação pronta para enviar à barbearia.</p></div>
      </div>
      <label className="flex gap-3 items-center"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /><span className="text-sm">Ativar confirmação pelo WhatsApp</span></label>
      <div><label className="text-sm font-medium">WhatsApp da barbearia</label><input className={input + " mt-1"} value={phone} onChange={e => setPhone(e.target.value)} placeholder="DDD + número" /><p className="text-xs text-muted-foreground mt-2">Não é necessário conectar a API da Meta. O cliente confirma o envio no próprio WhatsApp.</p></div>
      <button onClick={save} disabled={saving} className={btnPrimary}>{saving ? "Salvando..." : "Salvar configuração"}</button>
    </div>
  </div>;
}
