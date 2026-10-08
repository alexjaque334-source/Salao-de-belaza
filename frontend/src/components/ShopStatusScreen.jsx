import { useNavigate } from "react-router-dom";
import { LogOut, Clock, Ban, XCircle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { btnSecondary, card, overline } from "@/lib/styles";

const CONFIG = {
  pending: {
    icon: Clock, color: "text-amber-400", ring: "border-amber-500/30 bg-amber-500/10",
    title: "Cadastro em análise",
    text: "Sua barbearia foi cadastrada e está aguardando aprovação do administrador da plataforma. Você poderá acessar o painel assim que for aprovada.",
  },
  suspended: {
    icon: Ban, color: "text-rose-400", ring: "border-rose-500/30 bg-rose-500/10",
    title: "Barbearia suspensa",
    text: "O acesso da sua barbearia está suspenso no momento. Seus dados estão preservados e voltarão ao normal após a reativação. Entre em contato com o administrador da plataforma.",
  },
  rejected: {
    icon: XCircle, color: "text-rose-400", ring: "border-rose-500/30 bg-rose-500/10",
    title: "Cadastro não aprovado",
    text: "Infelizmente seu cadastro não foi aprovado. Entre em contato com o administrador da plataforma para mais informações.",
  },
};

export function ShopStatusScreen({ status, shopName, shopCode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const cfg = CONFIG[status] || CONFIG.pending;
  const Icon = cfg.icon;

  const doLogout = () => { logout(); navigate("/login"); };

  return (
    <div className="min-h-screen grid place-items-center bg-background text-foreground p-6">
      <div className={card + " max-w-lg w-full p-8 text-center animate-[fade-up_0.5s_ease]"} data-testid="shop-status-screen">
        <div className={`h-16 w-16 rounded-2xl grid place-items-center mx-auto border ${cfg.ring}`}>
          <Icon className={`h-8 w-8 ${cfg.color}`} />
        </div>
        <div className={overline + " mt-5"}>{shopName || "Sua barbearia"}</div>
        <h1 className="font-display text-3xl font-extrabold mt-2">{cfg.title}</h1>
        <p className="text-muted-foreground mt-3 text-sm leading-relaxed">{cfg.text}</p>
        {shopCode && (
          <div className="mt-5 inline-flex items-center gap-2 rounded-xl bg-secondary border border-border px-4 py-2 text-sm">
            Código da barbearia: <span className="font-display font-bold text-amber-400 tracking-widest">{shopCode}</span>
          </div>
        )}
        <div className="mt-7">
          <button data-testid="status-logout-btn" onClick={doLogout} className={btnSecondary}>
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </div>
      </div>
    </div>
  );
}
