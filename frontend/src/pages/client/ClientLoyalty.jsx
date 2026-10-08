import { useEffect, useState } from "react";
import { Crown, Gift, Star, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/PageHeader";
import { card, badge, tierColors, overline } from "@/lib/styles";

const NEXT = 100;
const TIERS = ["Bronze", "Silver", "Gold", "VIP Black"];

export default function ClientLoyalty() {
  const { user, setUser } = useAuth();
  const [me, setMe] = useState(user);

  useEffect(() => {
    api.get("/auth/me").then((r) => { setMe(r.data); setUser(r.data); });
  }, []);

  const progress = Math.min(100, Math.round((me.points % NEXT) / NEXT * 100));
  const toNext = NEXT - (me.points % NEXT);

  return (
    <div>
      <PageHeader eyebrow="Recompensas" title="Minha Fidelidade" subtitle="Acumule pontos e ganhe cortes grátis." />

      <div className={card + " p-8 relative overflow-hidden mb-6"}>
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-amber-500/10 blur-2xl" />
        <div className="relative">
          <div className={overline}>Seu saldo</div>
          <div className="flex items-end gap-3 mt-2">
            <span className="font-display text-6xl font-extrabold text-amber-400">{me.points}</span>
            <span className="text-muted-foreground mb-2">pontos</span>
          </div>
          <div className="mt-3"><span className={badge(tierColors[me.tier] + " text-sm")}><Crown className="h-4 w-4 mr-1" /> {me.tier}</span></div>

          <div className="mt-6 max-w-md">
            <div className="flex justify-between text-sm text-muted-foreground mb-1.5">
              <span>Faltam <strong className="text-amber-400">{toNext}</strong> pts para 1 corte grátis</span>
              <span>{me.points % NEXT}/{NEXT}</span>
            </div>
            <div className="h-3 rounded-full bg-secondary overflow-hidden">
              <div className="h-full bg-gradient-to-r from-amber-600 to-amber-400 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-5">
        <div className={card + " p-6"}>
          <Sparkles className="h-6 w-6 text-amber-400 mb-3" />
          <div className="font-display text-lg font-bold">Como funciona</div>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            <li className="flex gap-2"><Star className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" /> Ganhe 10 pontos a cada atendimento concluído.</li>
            <li className="flex gap-2"><Gift className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" /> A cada 100 pontos, resgate 1 corte grátis na recepção.</li>
            <li className="flex gap-2"><Crown className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" /> Suba de nível: Bronze → Silver → Gold → VIP Black.</li>
          </ul>
        </div>
        <div className={card + " p-6"}>
          <div className="font-display text-lg font-bold mb-4">Níveis de Fidelidade</div>
          <div className="space-y-3">
            {TIERS.map((t, i) => (
              <div key={t} className="flex items-center justify-between">
                <span className={badge(tierColors[t])}>{t}</span>
                <span className="text-xs text-muted-foreground">{[0, 100, 300, 600][i]}+ pontos</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
