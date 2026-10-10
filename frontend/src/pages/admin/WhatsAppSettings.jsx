import { useEffect, useState } from "react";
import { MessageCircle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, card, input } from "@/lib/styles";

export default function WhatsAppSettings() {
  const [form, setForm] = useState({ phone: "", booking_enabled: true, plans_enabled: true });
  const [status, setStatus] = useState("not_connected");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/integrations/whatsapp").then(({ data }) => {
      setForm({ phone: data.phone || "", booking_enabled: data.booking_enabled !== false, plans_enabled: data.plans_enabled !== false });
      setStatus(data.status || "not_connected");
    }).catch(() => {});
  }, []);

  const save = async () => {
    try {
      setSaving(true);
      const { data } = await api.put("/integrations/whatsapp", form);
      setStatus(data.status);
      toast.success("Configuração do WhatsApp salva.");
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };

  return <div>
    <PageHeader eyebrow="Integrações" title="WhatsApp" subtitle="Prepare o número da barbearia para agendamentos e planos pelo WhatsApp." />
    <div className={card + " max-w-2xl p-6 space-y-5"}>
      <div className="flex items-start gap-3"><MessageCircle className="h-6 w-6 text-emerald-400 mt-0.5" /><div><div className="font-semibold">WhatsApp da barbearia</div><p className="text-sm text-muted-foreground mt-1">Cadastre o número que será usado pela integração oficial. A conexão com a Meta será ativada em uma etapa posterior.</p></div></div>
      <div><label className="text-sm font-medium">Número do WhatsApp</label><input className={input + " mt-1"} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="(41) 99999-9999" /></div>
      <label className="flex gap-3 items-center"><input type="checkbox" checked={form.booking_enabled} onChange={e => setForm({ ...form, booking_enabled: e.target.checked })} /><span className="text-sm">Permitir agendamentos pelo WhatsApp</span></label>
      <label className="flex gap-3 items-center"><input type="checkbox" checked={form.plans_enabled} onChange={e => setForm({ ...form, plans_enabled: e.target.checked })} /><span className="text-sm">Mostrar planos mensais pelo WhatsApp</span></label>
      <div className="rounded-xl border border-border p-4 flex gap-3"><ShieldCheck className="h-5 w-5 text-amber-400" /><div><div className="text-sm font-semibold">Status: {status === "connected" ? "Conectado" : status === "configured" ? "Número cadastrado" : "Não conectado"}</div><p className="text-xs text-muted-foreground mt-1">Nenhuma mensagem será enviada enquanto a integração oficial não estiver conectada.</p></div></div>
      <button onClick={save} disabled={saving} className={btnPrimary}>{saving ? "Salvando..." : "Salvar configuração"}</button>
    </div>
  </div>;
}
