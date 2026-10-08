import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Star, Crown } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, card, badge } from "@/lib/styles";

export default function ClientPlans() {
  const [plans, setPlans] = useState([]);
  const [mySubs, setMySubs] = useState([]);

  const load = () => {
    api.get("/plans").then((r) => setPlans(r.data));
    api.get("/subscriptions/me").then((r) => setMySubs(r.data));
  };
  useEffect(() => { load(); }, []);

  const active = mySubs.find((s) => s.status === "Ativo");

  const subscribe = async (plan_id) => {
    try { await api.post("/subscriptions", { plan_id }); toast.success("Plano assinado com sucesso!"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div>
      <PageHeader eyebrow="Assinaturas" title="Nossos Planos" subtitle="Economize e tenha benefícios exclusivos todo mês." />
      {active && (
        <div className={card + " p-5 mb-6 border-emerald-500/30 flex items-center gap-3"}>
          <Crown className="h-6 w-6 text-emerald-400" />
          <div>
            <div className="font-semibold">Você é assinante do {active.plan_name}</div>
            <div className="text-sm text-muted-foreground">Renova em {active.renewal_date?.split("-").reverse().join("/")}</div>
          </div>
        </div>
      )}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="client-plans-grid">
        {plans.map((p) => {
          const isActive = active?.plan_id === p.id;
          return (
            <div key={p.id} className={card + ` p-6 ${p.recommended ? "border-amber-500/50" : ""}`} data-testid={`client-plan-${p.id}`}>
              {p.recommended && <div className={badge("bg-amber-500/10 text-amber-400 border-amber-500/30 mb-3")}><Star className="h-3 w-3 mr-1" /> Recomendado</div>}
              <div className="font-display text-2xl font-extrabold">{p.name}</div>
              <div className="text-sm text-muted-foreground mt-1">{p.description}</div>
              <div className="mt-4 flex items-end gap-1">
                <span className="font-display text-4xl font-extrabold text-amber-400">R$ {p.price}</span>
                <span className="text-muted-foreground text-sm mb-1">/mês</span>
              </div>
              <div className="text-xs text-amber-500/90 font-semibold mt-1">{p.cuts_per_month}</div>
              <ul className="mt-4 space-y-2">
                {(p.features || []).map((f, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-muted-foreground"><Check className="h-4 w-4 text-emerald-400 shrink-0" /> {f}</li>
                ))}
              </ul>
              <button data-testid={`subscribe-plan-${p.id}`} disabled={isActive} onClick={() => subscribe(p.id)} className={btnPrimary + " w-full mt-5"}>
                {isActive ? "Plano Atual" : "Assinar Agora"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
