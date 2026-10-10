import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Scissors, Eye, EyeOff, Store, ArrowLeft } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { btnPrimary, input, overline } from "@/lib/styles";

export default function Login() {
  const { authenticate } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login"); // login | request-access
  const [form, setForm] = useState({ shop_code: "", shop_name: "", name: "", email: "", password: "", phone: "", cpf_cnpj: "", platform_plan_id: "" });
  const [plans, setPlans] = useState([]);
  const [requestStep, setRequestStep] = useState("plan");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState(null); // {code, message}

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    if (mode === "request-access") {
      api.get("/public/platform-plans").then((r) => setPlans(r.data)).catch(() => toast.error("Não foi possível carregar os planos."));
    }
  }, [mode]);

  const goAfter = (data) => {
    authenticate(data.token, data.user);
    navigate(data.user.role === "admin" ? "/dashboard" : "/agendar");
  };

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "request-access") {
        const { data } = await api.post("/auth/request-access", {
          shop_name: form.shop_name, name: form.name, email: form.email,
          password: form.password, phone: form.phone, cpf_cnpj: form.cpf_cnpj, platform_plan_id: form.platform_plan_id,
        });
        setPending({ code: data.shop_code, message: data.message, slug: data.public_slug, plan: data.platform_plan_name });
        toast.success("Solicitação enviada!");
      } else {
        const { data } = await api.post("/auth/login", {
          shop_code: form.shop_code, email: form.email, password: form.password,
        });
        toast.success("Bem-vindo de volta!");
        goAfter(data);
      }
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  const titles = {
    login: "Entrar na conta",
    "request-access": "Solicitar acesso para minha barbearia",
  };
  const subtitles = {
    login: "Informe o código da barbearia, e-mail e senha.",
    "request-access": "Preencha os dados; seu cadastro passará por aprovação.",
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
            Cada barbearia com seus próprios barbeiros, clientes e agenda — totalmente separados.
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

          <h2 className="font-display text-3xl font-bold">{titles[mode]}</h2>
          <p className="text-muted-foreground mt-2 text-sm">{subtitles[mode]}</p>

          {pending && (
            <div data-testid="pending-request-box" className="mt-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
              <div className={overline}>Cadastro em análise</div>
              <p className="text-sm text-foreground mt-2">{pending.message}</p>
              <div className="mt-3 text-sm text-muted-foreground">Código da sua barbearia:</div>
              <div className="font-display text-2xl font-extrabold text-amber-400 tracking-[0.3em]">{pending.code}</div>
              <p className="text-xs text-muted-foreground mt-2">Plano selecionado: <strong>{pending.plan}</strong>. Guarde este código para acessar sua conta. Seu link público será <strong>/agendar/{pending.slug}</strong> quando a barbearia estiver ativa.</p>
              <button data-testid="pending-back-btn" onClick={() => { setPending(null); setMode("login"); }} className={btnPrimary + " w-full mt-4"}>Voltar para entrar</button>
            </div>
          )}

          {!pending && mode === "request-access" && requestStep === "plan" && (
            <div className="mt-7 space-y-4">
              <div className="grid gap-3">
                {plans.map((plan) => (
                  <button key={plan.id} type="button" onClick={() => setForm({ ...form, platform_plan_id: plan.id })}
                    className={`text-left rounded-xl border p-4 transition-all ${form.platform_plan_id === plan.id ? "border-amber-500 bg-amber-500/10" : "border-border bg-card hover:border-amber-500/40"}`}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-display font-bold text-lg">{plan.name}</div>
                      <div className="font-bold text-amber-400">R$ {Number(plan.monthly_price).toFixed(2).replace(".", ",")}<span className="text-xs text-muted-foreground">/mês</span></div>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">{plan.description}</div>
                    <div className="text-xs text-muted-foreground mt-3">
                      {plan.max_professionals == null ? "Profissionais ilimitados" : `Até ${plan.max_professionals} profissionais`} · {plan.max_services == null ? "Serviços ilimitados" : `Até ${plan.max_services} serviços`} · {plan.max_client_plans == null ? "Planos de clientes ilimitados" : `Até ${plan.max_client_plans} planos de clientes`}{plan.pdf_reports ? " · PDF mensal" : ""}
                    </div>
                  </button>
                ))}
              </div>
              <button type="button" disabled={!form.platform_plan_id} onClick={() => setRequestStep("details")} className={btnPrimary + " w-full disabled:opacity-50"}>Continuar com este plano</button>
            </div>
          )}

          {!pending && (mode !== "request-access" || requestStep === "details") && (
          <form onSubmit={submit} className="mt-7 space-y-4">
            {mode === "request-access" && (
              <>
                <button type="button" onClick={() => setRequestStep("plan")} className="text-sm text-amber-500 font-semibold hover:underline">← Trocar plano</button>
                <div>
                  <label className="text-sm font-medium">Nome da barbearia</label>
                  <input data-testid="shop-name-input" className={input + " mt-1.5"} value={form.shop_name} onChange={upd("shop_name")} required placeholder="Ex: Barbearia do João" />
                </div>
                <div>
                  <label className="text-sm font-medium">CPF ou CNPJ</label>
                  <input data-testid="cpf-cnpj-input" className={input + " mt-1.5"} value={form.cpf_cnpj} onChange={upd("cpf_cnpj")} required placeholder="000.000.000-00 ou 00.000.000/0000-00" />
                </div>
              </>
            )}

            {mode === "login" && (
              <div>
                <label className="text-sm font-medium flex items-center gap-1.5"><Store className="h-3.5 w-3.5 text-amber-500" /> Código da barbearia</label>
                <input data-testid="shop-code-input" className={input + " mt-1.5 uppercase tracking-widest"} value={form.shop_code} onChange={(e) => setForm({ ...form, shop_code: e.target.value.toUpperCase() })} required placeholder="EX: DEMO01" />
              </div>
            )}

            {mode !== "login" && (
              <div>
                <label className="text-sm font-medium">{mode === "request-access" ? "Nome do responsável" : "Nome completo"}</label>
                <input data-testid="register-name-input" className={input + " mt-1.5"} value={form.name} onChange={upd("name")} required placeholder="Seu nome" />
              </div>
            )}

            <div>
              <label className="text-sm font-medium">E-mail</label>
              <input data-testid="login-email-input" type="email" className={input + " mt-1.5"} value={form.email} onChange={upd("email")} required placeholder="voce@email.com" />
            </div>

            {mode !== "login" && (
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
              {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Solicitar acesso"}
            </button>
          </form>
          )}

          {!pending && (
          <div className="mt-6 space-y-2 text-center text-sm text-muted-foreground">
            {mode === "login" && (
              <>
                <p>
                  É dono de barbearia?{" "}
                  <button data-testid="go-create-shop-btn" onClick={() => { setMode("request-access"); setRequestStep("plan"); }} className="text-amber-500 font-semibold hover:underline">Solicitar acesso para minha barbearia</button>
                </p>
              </>
            )}
            {mode !== "login" && (
              <button data-testid="back-to-login-btn" onClick={() => { setMode("login"); setPending(null); }} className="inline-flex items-center gap-1 text-amber-500 font-semibold hover:underline">
                <ArrowLeft className="h-4 w-4" /> Voltar para entrar
              </button>
            )}
          </div>
          )}
        </div>
      </div>
    </div>
  );
}
