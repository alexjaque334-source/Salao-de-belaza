import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CalendarDays, DollarSign, Users, Crown, TrendingUp, Trophy, Clock, Sparkles, ArrowRight, MessageCircle,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, Tooltip, CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { card, overline, badge, statusColors } from "@/lib/styles";

const fmt = (n) => `R$ ${Number(n || 0).toLocaleString("pt-BR")}`;

function Stat({ icon: Icon, label, value, accent }) {
  return (
    <div className={card + " p-5 hover:border-amber-500/40 transition-all"}>
      <div className="flex items-start justify-between">
        <div>
          <div className={overline}>{label}</div>
          <div className="font-display text-3xl font-extrabold mt-2">{value}</div>
        </div>
        <div className={`h-10 w-10 rounded-xl grid place-items-center ${accent}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
  }, []);

  if (!stats) return <div className="text-muted-foreground">Carregando painel...</div>;

  return (
    <div>
      <PageHeader eyebrow="Visão Geral" title="Painel da Barbearia" subtitle="Resumo do desempenho e próximos atendimentos." />

      <div className="mb-6 rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-amber-600/5 to-transparent p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-500/20 text-amber-400 grid place-items-center shrink-0">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="font-display font-bold text-base text-foreground flex items-center gap-2">
              Assistente CRM Ativo
              <span className="text-[10px] uppercase font-bold tracking-wider bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full">
                Copiloto
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Identifique clientes inativos (+45 dias), aniversariantes da semana e fidelizados para resgate com mensagens prontas para WhatsApp.
            </p>
          </div>
        </div>
        <Link
          to="/assistente-crm"
          className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 transition-all shrink-0 self-start sm:self-auto shadow-md shadow-amber-900/30"
        >
          Abrir Assistente CRM <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6" data-testid="dashboard-stats">
        <Stat icon={CalendarDays} label="Agendamentos Hoje" value={stats.appts_today} accent="bg-amber-500/10 text-amber-400" />
        <Stat icon={DollarSign} label="Receita do Mês" value={fmt(stats.revenue_month)} accent="bg-emerald-500/10 text-emerald-400" />
        <Stat icon={Users} label="Total de Clientes" value={stats.total_clients} accent="bg-blue-500/10 text-blue-400" />
        <Stat icon={Crown} label="Assinantes Ativos" value={stats.active_subs} accent="bg-amber-500/10 text-amber-400" />
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className={card + " p-6 lg:col-span-2"}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className={overline}>Últimos 7 dias</div>
              <h3 className="font-display text-xl font-bold mt-1">Receita Diária</h3>
            </div>
            <TrendingUp className="h-5 w-5 text-amber-500" />
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={stats.series}>
              <defs>
                <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="date" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: "#121216", border: "1px solid #27272a", borderRadius: 12, color: "#fff" }} formatter={(v) => fmt(v)} />
              <Area type="monotone" dataKey="revenue" stroke="#f59e0b" strokeWidth={2.5} fill="url(#rev)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-6">
          <div className={card + " p-6"}>
            <div className={overline}>Destaque do Mês</div>
            <div className="flex items-center gap-3 mt-3">
              <div className="h-12 w-12 rounded-xl bg-amber-500/10 grid place-items-center">
                <Trophy className="h-6 w-6 text-amber-400" />
              </div>
              <div>
                <div className="font-display text-lg font-bold">{stats.top_barber}</div>
                <div className="text-xs text-muted-foreground">Barbeiro com maior receita</div>
              </div>
            </div>
          </div>
          <div className={card + " p-6"}>
            <div className={overline}>Receita Total Acumulada</div>
            <div className="font-display text-3xl font-extrabold mt-2 text-emerald-400">{fmt(stats.revenue_total)}</div>
            <div className="text-xs text-muted-foreground mt-1">{stats.total_barbers} barbeiros ativos</div>
          </div>
        </div>
      </div>

      <div className={card + " p-6 mt-6"}>
        <div className="flex items-center gap-2 mb-4">
          <Clock className="h-5 w-5 text-amber-500" />
          <h3 className="font-display text-xl font-bold">Próximos Atendimentos</h3>
        </div>
        {stats.upcoming.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">Nenhum agendamento futuro.</div>
        ) : (
          <div className="space-y-2">
            {stats.upcoming.map((a) => {
              let digits = (a.client_phone || "").replace(/\D/g, "");
              if (digits && digits.length <= 11 && !digits.startsWith("55")) digits = "55" + digits;
              const nome = (a.client_name || "").split(" ")[0];
              const msg = `Olá ${nome}! 👋 Lembrete do seu horário na BarberStudio hoje às ${a.time} (${a.service_name} com ${a.barber_name}). Tudo confirmado? Até logo! ✂️`;
              const waUrl = digits ? `https://wa.me/${digits}?text=${encodeURIComponent(msg)}` : null;

              return (
                <div key={a.id} className="flex items-center justify-between py-3 px-4 rounded-xl bg-secondary/40 border border-border">
                  <div className="flex items-center gap-4">
                    <div className="text-center min-w-[52px]">
                      <div className="font-display font-bold text-amber-400">{a.time}</div>
                      <div className="text-[10px] text-muted-foreground">{a.date.split("-").reverse().slice(0, 2).join("/")}</div>
                    </div>
                    <div>
                      <div className="font-semibold text-sm">{a.client_name}</div>
                      <div className="text-xs text-muted-foreground">{a.service_name} • {a.barber_name}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={badge(statusColors[a.status])}>{a.status}</span>
                    {waUrl && a.status === "Confirmado" && (
                      <a
                        href={waUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Enviar lembrete WhatsApp"
                        className="p-1.5 rounded-lg text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                      >
                        <MessageCircle className="h-4 w-4" />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
