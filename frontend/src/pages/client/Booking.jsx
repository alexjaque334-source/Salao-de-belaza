import { PageHeader } from "@/components/PageHeader";
import { BookingWizard } from "@/components/BookingWizard";
import { useAuth } from "@/context/AuthContext";
import { card, overline } from "@/lib/styles";

export default function Booking() {
  const { user } = useAuth();
  return (
    <div>
      <PageHeader eyebrow={`Olá, ${user.name.split(" ")[0]}`} title="Agendar Horário" subtitle="Escolha o barbeiro, o serviço e o melhor horário para você." />
      <div
        className="rounded-2xl overflow-hidden mb-6 relative h-40 sm:h-52 bg-cover bg-center border border-border"
        style={{ backgroundImage: "linear-gradient(to right, rgba(10,10,12,0.85), rgba(10,10,12,0.3)), url('https://images.unsplash.com/photo-1621605815971-fbc98d665033?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400')" }}
      >
        <div className="absolute bottom-5 left-6">
          <div className={overline}>Experiência Premium</div>
          <div className="font-display text-2xl sm:text-3xl font-extrabold mt-1">Seu estilo, nossa precisão</div>
        </div>
      </div>
      <div className={card + " p-6"}>
        <BookingWizard isAdmin={false} />
      </div>
    </div>
  );
}
