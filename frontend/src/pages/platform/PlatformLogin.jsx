import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ShieldCheck, Eye, EyeOff } from "lucide-react";
import { platformApi } from "@/lib/platformApi";
import { apiError } from "@/lib/api";
import { btnPrimary, input, overline, card } from "@/lib/styles";

export default function PlatformLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await platformApi.post("/platform/login", { email, password });
      localStorage.setItem("platform_token", data.token);
      toast.success("Bem-vindo à Administração da Plataforma");
      navigate("/plataforma/painel");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-background text-foreground p-6">
      <div className={card + " max-w-md w-full p-8 animate-[fade-up_0.5s_ease]"}>
        <div className="flex items-center gap-2.5 mb-6">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 grid place-items-center">
            <ShieldCheck className="h-5 w-5 text-zinc-950" />
          </div>
          <span className="font-display font-extrabold text-lg">Administração da Plataforma</span>
        </div>
        <div className={overline}>Acesso restrito</div>
        <h1 className="font-display text-2xl font-bold mt-1">Entrar como Super Admin</h1>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label className="text-sm font-medium">E-mail</label>
            <input data-testid="platform-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input + " mt-1.5"} placeholder="dono@plataforma.com" />
          </div>
          <div>
            <label className="text-sm font-medium">Senha</label>
            <div className="relative mt-1.5">
              <input data-testid="platform-password-input" type={show ? "text" : "password"} required value={password} onChange={(e) => setPassword(e.target.value)} className={input} placeholder="••••••••" />
              <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <button data-testid="platform-login-btn" type="submit" disabled={loading} className={btnPrimary + " w-full"}>
            {loading ? "Aguarde..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
