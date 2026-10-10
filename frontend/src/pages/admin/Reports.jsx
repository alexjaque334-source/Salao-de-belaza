import { useEffect, useState } from "react";
import { DollarSign, Scissors, TrendingUp, Percent, FileDown } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { card, overline, badge } from "@/lib/styles";

const fmt = (n) => `R$ ${Number(n || 0).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

function monthLabel(m) {
  const [y, mo] = m.split("-");
  const names = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
  return `${names[Number(mo) - 1]} / ${y}`;
}

export default function Reports() {
  const now = new Date().toISOString().slice(0, 7);
  const [month, setMonth] = useState(now);
  const [data, setData] = useState(null);
  const [capabilities, setCapabilities] = useState({ pdf_reports: false, platform_plan_name: "" });

  useEffect(() => {
    api.get(`/reports/barbers?month=${month}`).then((r) => setData(r.data)).catch(() => {});
  }, [month]);

  useEffect(() => {
    api.get("/reports/capabilities").then((r) => setCapabilities(r.data)).catch(() => {});
  }, []);

  const exportPdf = () => {
    if (!capabilities.pdf_reports) return;
    window.print();
  };

  return (
    <div>
      <PageHeader
        eyebrow="Desempenho"
        title="Relatório por Barbeiro"
        subtitle="Atendimentos, receita e comissão de cada barbeiro no mês."
        action={
          <input
            data-testid="report-month-input"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="bg-input/60 border border-border rounded-xl px-3 py-2.5 text-sm outline-none focus:border-amber-500"
          />
        }
      />

      {!data ? (
        <div className="text-muted-foreground">Carregando relatório...</div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
            <div className="text-sm text-muted-foreground">Período: <span className="text-amber-400 font-semibold">{monthLabel(data.month)}</span></div>
            {capabilities.pdf_reports ? (
              <button onClick={exportPdf} className="print:hidden inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold bg-amber-500 text-zinc-950 hover:bg-amber-400">
                <FileDown className="h-4 w-4" /> Exportar / salvar em PDF
              </button>
            ) : (
              <div className="print:hidden text-xs text-muted-foreground">Exportação em PDF disponível no plano Premium.</div>
            )}
          </div>

          <div className="grid sm:grid-cols-3 gap-5 mb-6">
            <div className={card + " p-5"}>
              <div className={overline}>Receita do Mês</div>
              <div className="font-display text-3xl font-extrabold mt-2 text-emerald-400">{fmt(data.totals.revenue)}</div>
            </div>
            <div className={card + " p-5"}>
              <div className={overline}>Comissões a Pagar</div>
              <div className="font-display text-3xl font-extrabold mt-2 text-amber-400">{fmt(data.totals.commission)}</div>
            </div>
            <div className={card + " p-5"}>
              <div className={overline}>Atendimentos Concluídos</div>
              <div className="font-display text-3xl font-extrabold mt-2">{data.totals.completed}</div>
            </div>
          </div>

          {data.report.every((r) => r.completed === 0) && (
            <div className={card + " p-10 text-center text-muted-foreground mb-6"}>
              Nenhum atendimento concluído neste mês. Conclua agendamentos na aba Agendamentos para gerar o relatório.
            </div>
          )}

          <div className="grid lg:grid-cols-2 gap-5" data-testid="barber-reports-grid">
            {data.report.map((r) => (
              <div key={r.barber_id} className={card + " p-6"} data-testid={`report-card-${r.barber_id}`}>
                <div className="flex items-center gap-4 mb-5">
                  {r.avatar ? (
                    <img src={r.avatar} alt={r.name} className="h-14 w-14 rounded-xl object-cover border border-border" />
                  ) : (
                    <div className="h-14 w-14 rounded-xl bg-amber-500/10 grid place-items-center"><Scissors className="h-6 w-6 text-amber-400" /></div>
                  )}
                  <div className="flex-1">
                    <div className="font-display font-bold text-lg">{r.name}</div>
                    <div className="text-sm text-amber-400">{r.specialty}</div>
                  </div>
                  <span className={badge("bg-amber-500/10 text-amber-400 border-amber-500/20")}><Percent className="h-3 w-3 mr-1" /> {r.commission_rate}%</span>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-5">
                  <div className="rounded-xl bg-secondary/40 border border-border p-3">
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground uppercase tracking-wide"><Scissors className="h-3 w-3" /> Cortes</div>
                    <div className="font-display text-xl font-bold mt-1">{r.completed}</div>
                  </div>
                  <div className="rounded-xl bg-secondary/40 border border-border p-3">
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground uppercase tracking-wide"><DollarSign className="h-3 w-3" /> Receita</div>
                    <div className="font-display text-xl font-bold mt-1 text-emerald-400">{fmt(r.revenue)}</div>
                  </div>
                  <div className="rounded-xl bg-amber-500/5 border border-amber-500/20 p-3">
                    <div className="flex items-center gap-1 text-[11px] text-amber-500/80 uppercase tracking-wide"><TrendingUp className="h-3 w-3" /> Comissão</div>
                    <div className="font-display text-xl font-bold mt-1 text-amber-400">{fmt(r.commission)}</div>
                  </div>
                </div>

                <div className="text-xs text-muted-foreground mb-2">Ticket médio: <span className="text-foreground font-semibold">{fmt(r.avg_ticket)}</span></div>
                {r.services.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {r.services.map((s) => (
                      <span key={s.name} className={badge("bg-secondary text-foreground border-border")}>{s.name} · {s.count}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
