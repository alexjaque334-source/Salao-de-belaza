export function PageHeader({ eyebrow, title, subtitle, action }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6 sm:mb-8">
      <div className="animate-[fade-up_0.4s_ease]">
        {eyebrow && <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-amber-500/90">{eyebrow}</div>}
        <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">{title}</h1>
        {subtitle && <p className="text-muted-foreground mt-1.5 text-sm">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
