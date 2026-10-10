import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Scissors, Power, PowerOff } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, btnSecondary, card, input, badge } from "@/lib/styles";

const emptyForm = { name: "", duration: 30, price: "" };

export default function Services() {
  const [services, setServices] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [changingId, setChangingId] = useState(null);
  const [view, setView] = useState("active");

  const load = async () => {
    try {
      const response = await api.get("/services");
      setServices(response.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setOpen(true);
  };

  const openEdit = (service) => {
    setEditing(service);
    setForm({
      name: service.name,
      duration: service.duration,
      price: String(service.price),
    });
    setOpen(true);
  };

  const save = async () => {
    const name = form.name.trim();
    const duration = Number(form.duration);
    const price = Number(form.price);

    if (!name) {
      toast.error("Informe o nome do serviço.");
      return;
    }

    if (
      String(form.duration).trim() === "" ||
      !Number.isInteger(duration) ||
      duration <= 0
    ) {
      toast.error("Informe uma duração válida em minutos.");
      return;
    }

    if (
      String(form.price).trim() === "" ||
      !Number.isFinite(price) ||
      price < 0
    ) {
      toast.error("Informe um preço válido.");
      return;
    }

    const payload = { name, duration, price };

    setSaving(true);

    try {
      if (editing) {
        await api.put(`/services/${editing.id}`, payload);
      } else {
        await api.post("/services", payload);
      }

      toast.success(
        editing ? "Serviço atualizado" : "Serviço cadastrado"
      );

      setOpen(false);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (service) => {
    if (changingId) return;

    setChangingId(service.id);

    try {
      await api.patch(`/services/${service.id}/status`);

      toast.success(
        service.active === false
          ? "Serviço reativado"
          : "Serviço desativado"
      );

      await load();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setChangingId(null);
    }
  };

  const visibleServices = services.filter((service) =>
    view === "active" ? service.active !== false : service.active === false
  );

  const formatPrice = (value) =>
    Number(value || 0).toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });

  return (
    <div>
      <PageHeader
        eyebrow="Gerenciamento"
        title="Serviços"
        subtitle="Cadastre, edite e gerencie os serviços da barbearia."
        action={
          <button
            data-testid="add-service-btn"
            onClick={openNew}
            className={btnPrimary}
          >
            <Plus className="h-4 w-4" />
            Novo Serviço
          </button>
        }
      />

      <div className="flex gap-2 mb-5">
        <button onClick={() => setView("active")} className={view === "active" ? btnPrimary : btnSecondary}>Serviços ativos</button>
        <button onClick={() => setView("inactive")} className={view === "inactive" ? btnPrimary : btnSecondary}>Serviços desativados</button>
      </div>

      {services.length === 0 ? (
        <div className={card + " p-8 text-center"}>
          <Scissors className="h-10 w-10 text-amber-400 mx-auto mb-3" />
          <p className="font-semibold">
            Nenhum serviço cadastrado
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            Clique em Novo Serviço para começar.
          </p>
        </div>
      ) : (
        <div
          className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5"
          data-testid="services-grid"
        >
          {visibleServices.map((service) => {
            const active = service.active !== false;

            return (
              <div
                key={service.id}
                className={
                  card +
                  " p-5 hover:border-amber-500/40 transition-all"
                }
                data-testid={`service-card-${service.id}`}
              >
                <div className="flex items-start gap-3">
                  <div className="h-12 w-12 rounded-xl bg-amber-500/10 grid place-items-center">
                    <Scissors className="h-6 w-6 text-amber-400" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="font-display font-bold text-lg">
                      {service.name}
                    </div>

                    <div className="text-sm text-muted-foreground mt-1">
                      {service.duration} minutos
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between mt-5">
                  <span className="text-xl font-bold text-amber-400">
                    {formatPrice(service.price)}
                  </span>

                  <span
                    className={badge(
                      active
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                    )}
                  >
                    {active ? "Ativo" : "Inativo"}
                  </span>
                </div>

                <div className="flex gap-2 mt-5">
                  <button
                    data-testid={`edit-service-${service.id}`}
                    onClick={() => openEdit(service)}
                    className={btnSecondary + " flex-1"}
                  >
                    <Pencil className="h-4 w-4" />
                    Editar
                  </button>

                  <button
                    data-testid={`status-service-${service.id}`}
                    onClick={() => changeStatus(service)}
                    disabled={changingId !== null}
                    className={
                      "flex items-center justify-center gap-2 px-3 rounded-xl border border-border " +
                      (active
                        ? "text-rose-400 hover:bg-rose-500/10"
                        : "text-emerald-400 hover:bg-emerald-500/10") +
                      " disabled:opacity-50"
                    }
                    title={active ? "Desativar serviço" : "Reativar serviço"}
                  >
                    {active ? (
                      <PowerOff className="h-4 w-4" />
                    ) : (
                      <Power className="h-4 w-4" />
                    )}
                    {active ? "Desativar" : "Reativar"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg bg-card border-border">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl">
              {editing ? "Editar Serviço" : "Novo Serviço"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">
                Nome do serviço
              </label>
              <input
                data-testid="service-name-input"
                className={input + " mt-1"}
                placeholder="Ex.: Corte masculino"
                value={form.name}
                onChange={(e) =>
                  setForm({ ...form, name: e.target.value })
                }
              />
            </div>

            <div>
              <label className="text-sm font-medium">
                Duração (minutos)
              </label>
              <input
                data-testid="service-duration-input"
                type="number"
                min="1"
                step="1"
                className={input + " mt-1"}
                value={form.duration}
                onChange={(e) =>
                  setForm({ ...form, duration: e.target.value })
                }
              />
            </div>

            <div>
              <label className="text-sm font-medium">
                Preço (R$)
              </label>
              <input
                data-testid="service-price-input"
                type="number"
                min="0"
                step="0.01"
                className={input + " mt-1"}
                placeholder="Ex.: 35.00"
                value={form.price}
                onChange={(e) =>
                  setForm({ ...form, price: e.target.value })
                }
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setOpen(false)}
                className={btnSecondary}
                disabled={saving}
              >
                Cancelar
              </button>

              <button
                data-testid="save-service-btn"
                onClick={save}
                className={btnPrimary}
                disabled={saving}
              >
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
