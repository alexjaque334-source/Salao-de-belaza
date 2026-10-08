import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Crown, Gift, Star, TrendingUp } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, btnSecondary, card, badge, tierColors, overline } from "@/lib/styles";

const NEXT = 100; // points for a free cut

export default function Loyalty() {
  const [clients, setClients] = useState([]);

  const load = () => api.get("/clients").then((r) => setClients(r.data.sort((a, b) => b.points - a.points)));
  useEffect(() => { load(); }, []);

  const redeem = async (id) => {
    try { const r = await api.post(`/clients/${id}/redeem`); toast.success(r.data.message); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const adjust = async (id, points) => {
    try { await api.patch(`/clients/${id}/loyalty`, { points }); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const vipCount = clients.filter((c) => c.tier === "VIP Black" || c.tier === "Gold").length;
  const totalPoints = clients.reduce((s, c) => s + c.points, 0);

  return (
    <div>
      <PageHeader eyebrow="Fidelidade" title="Clientes Fidelizados" subtitle="Programa de pontos e recompensas VIP." />

      <div className="grid sm:grid-cols-3 gap-5 mb-6">
        <div className={card + " p-5"}><div className={overline}>Clientes Fidelizados</div><div className="font-display text-3xl font-extrabold mt-2">{clients.length}</div></div>
        <div className={card + " p-5"}><div className={overline}>Membros VIP / Gold</div><div className="font-display text-3xl font-extrabold mt-2 text-amber-400">{vipCount}</div></div>
        <div className={card + " p-5"}><div className={overline}>Pontos em Circulação</div><div className="font-display text-3xl font-extrabold mt-2 text-emerald-400">{totalPoints}</div></div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="loyalty-grid">
        {clients.map((c) => {
          const progress = Math.min(100, Math.round((c.points % NEXT) / NEXT * 100));
          return (
            <div key={c.id} className={card + " p-5"} data-testid={`loyalty-card-${c.id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-amber-500/20 to-amber-700/10 grid place-items-center">
                    <Crown className="h-5 w-5 text-amber-400" />
                  </div>
                  <div>
                    <div className="font-semibold">{c.name}</div>
                    <span className={badge(tierColors[c.tier])}>{c.tier}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-display text-2xl font-extrabold text-amber-400">{c.points}</div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wide">pontos</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                  <span>Próximo corte grátis</span><span>{c.points % NEXT}/{NEXT}</span>
                </div>
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-amber-600 to-amber-400 transition-all" style={{ width: `${progress}%` }} />
                </div>
              </div>

              <div className="flex gap-2 mt-4">
                <button data-testid={`loyalty-add-${c.id}`} onClick={() => adjust(c.id, c.points + 10)} className={btnSecondary + " flex-1"}><Star className="h-4 w-4" /> +10</button>
                <button data-testid="loyalty-redeem-btn" onClick={() => redeem(c.id)} disabled={c.points < NEXT} className={btnPrimary + " flex-1"}><Gift className="h-4 w-4" /> Resgatar</button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
