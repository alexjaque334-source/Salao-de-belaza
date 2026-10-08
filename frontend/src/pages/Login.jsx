import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Scissors, Eye, EyeOff } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { btnPrimary, input, overline } from "@/lib/styles";

export default function Login() {
  const { authenticate } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "" });
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const payload =
        mode === "login"
          ? { email: form.email, password: form.password }
          : form;
      const { data } = await api.post(path, payload);
      authenticate(data.token, data.user);
      toast.success(mode === "login" ? "Bem-vindo de volta!" : "Conta criada com sucesso!");
      navigate(data.user.role === "admin" ? "/dashboard" : "/agendar");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background text-foreground">
      <div
        className="hidden lg:block relative bg-cover bg-center"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(10,10,12,0.4), rgba(10,10,12,0.95)), url('https://images.unsplash.com/photo-1585747860715-2ba37e788b70?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400')",
        }}
      >
        <div className="absolute bottom-0 p-12">
          <div className={overline}>Gestão Premium de Barbearia</div>
          <h1 className="font-display text-5xl font-extrabold mt-3 leading-tight">
            Estilo, precisão<br />e <span className="text-amber-500">fidelidade</span>.
          </h1>
          <p className="text-zinc-400 mt-4 max-w-md">
            Agende com seu barbeiro favorito, acompanhe pontos de fidelidade e aproveite planos exclusivos.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md animate-[fade-up_0.5s_ease]">
          <div className="flex items-center gap-2.5 mb-8">
            <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 grid place-items-center shadow-lg shadow-amber-900/40">
              <Scissors className="h-5 w-5 text-zinc-950" />
            </div>
            <span className="font-display font-extrabold text-xl">
              BARBER<span className="text-amber-500">STUDIO</span>
            </span>
          </div>

          <h2 className="font-display text-3xl font-bold">
            {mode === "login" ? "Entrar na conta" : "Criar conta"}
          </h2>
          <p className="text-muted-foreground mt-2 text-sm">
            {mode === "login"
              ? "Acesse o painel ou agende seu horário."
              : "Cadastre-se para agendar com os melhores barbeiros."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === "register" && (
              <div>
                <label className="text-sm font-medium">Nome completo</label>
                <input data-testid="register-name-input" className={input + " mt-1.5"} value={form.name} onChange={upd("name")} required placeholder="Seu nome" />
              </div>
            )}
            <div>
              <label className="text-sm font-medium">E-mail</label>
              <input data-testid="login-email-input" type="email" className={input + " mt-1.5"} value={form.email} onChange={upd("email")} required placeholder="voce@email.com" />
            </div>
            {mode === "register" && (
              <div>
                <label className="text-sm font-medium">Telefone</label>
                <input data-testid="register-phone-input" className={input + " mt-1.5"} value={form.phone} onChange={upd("phone")} placeholder="(11) 90000-0000" />
              </div>
            )}
            <div>
              <label className="text-sm font-medium">Senha</label>
              <div className="relative mt-1.5">
                <input data-testid="login-password-input" type={show ? "text" : "password"} className={input} value={form.password} onChange={upd("password")} required placeholder="••••••••" />
                <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button data-testid="login-submit-btn" type="submit" disabled={loading} className={btnPrimary + " w-full"}>
              {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Cadastrar"}
            </button>
          </form>

          <p className="text-center text-sm text-muted-foreground mt-6">
            {mode === "login" ? "Ainda não tem conta?" : "Já possui conta?"}{" "}
            <button
              data-testid="toggle-auth-mode-btn"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="text-amber-500 font-semibold hover:underline"
            >
              {mode === "login" ? "Cadastre-se" : "Entrar"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
