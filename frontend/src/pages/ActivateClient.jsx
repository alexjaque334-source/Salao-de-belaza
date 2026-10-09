import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { btnPrimary, card, input } from "@/lib/styles";

export default function ActivateClient() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!token) return toast.error("Link de ativação inválido.");
    if (password.length < 10 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      return toast.error("Use pelo menos 10 caracteres, com letras e números.");
    }
    if (password !== confirm) return toast.error("As senhas não coincidem.");
    try {
      setLoading(true);
      await api.post("/auth/activate-client", { token, password });
      toast.success("Conta ativada. Agora você já pode entrar.");
      navigate("/login", { replace: true });
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground grid place-items-center p-4">
      <form onSubmit={submit} className={card + " w-full max-w-md p-6 space-y-4"}>
        <div>
          <div className="text-xs uppercase tracking-wider text-amber-400 font-semibold">Ativação de conta</div>
          <h1 className="font-display text-2xl font-extrabold mt-1">Crie sua senha</h1>
          <p className="text-sm text-muted-foreground mt-2">Escolha uma senha com pelo menos 10 caracteres, incluindo letras e números.</p>
        </div>
        <div>
          <label className="text-sm font-medium">Nova senha</label>
          <input type="password" autoComplete="new-password" className={input + " mt-1"} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div>
          <label className="text-sm font-medium">Confirmar senha</label>
          <input type="password" autoComplete="new-password" className={input + " mt-1"} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <button type="submit" disabled={loading || !token} className={btnPrimary + " w-full justify-center disabled:opacity-60"}>
          {loading ? "Ativando..." : "Ativar minha conta"}
        </button>
        {!token && <p className="text-sm text-rose-400">Este link de ativação está incompleto.</p>}
      </form>
    </div>
  );
}
