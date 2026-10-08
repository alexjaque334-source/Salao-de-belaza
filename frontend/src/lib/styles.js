export const btnPrimary =
  "inline-flex items-center justify-center gap-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-zinc-950 font-bold px-5 py-2.5 rounded-xl shadow-lg shadow-amber-950/30 transition-all duration-200 active:scale-[0.98] border border-amber-400/40 disabled:opacity-50 disabled:cursor-not-allowed text-sm";
export const btnSecondary =
  "inline-flex items-center justify-center gap-2 bg-secondary hover:bg-muted text-foreground font-semibold px-4 py-2.5 rounded-xl border border-border transition-all duration-200 active:scale-[0.98] text-sm";
export const btnGhost =
  "inline-flex items-center justify-center gap-2 text-muted-foreground hover:text-amber-400 hover:bg-secondary px-3 py-2 rounded-lg transition-colors text-sm";
export const card =
  "bg-card border border-border rounded-2xl shadow-xl shadow-black/20 relative overflow-hidden";
export const input =
  "w-full bg-input/60 border border-border focus:border-amber-500 focus:ring-1 focus:ring-amber-500/50 text-foreground placeholder-muted-foreground rounded-xl px-4 py-2.5 text-sm transition-all outline-none";
export const overline =
  "text-[11px] font-bold uppercase tracking-[0.2em] text-amber-500/90";

export const tierColors = {
  Bronze: "bg-amber-900/30 text-amber-600 border-amber-800/40",
  Silver: "bg-zinc-400/10 text-zinc-300 border-zinc-500/30",
  Gold: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  "VIP Black": "bg-gradient-to-r from-zinc-800 to-zinc-900 text-amber-400 border-amber-500/40",
};

export const statusColors = {
  Confirmado: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  Concluído: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Cancelado: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  "Não Compareceu": "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
};

export function badge(cls) {
  return `inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${cls}`;
}

export const WEEKDAY_LABELS = {
  mon: "Segunda", tue: "Terça", wed: "Quarta", thu: "Quinta",
  fri: "Sexta", sat: "Sábado", sun: "Domingo",
};
export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
