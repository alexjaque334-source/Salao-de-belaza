import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Shell } from "@/components/Shell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/admin/Dashboard";
import Appointments from "@/pages/admin/Appointments";
import Barbers from "@/pages/admin/Barbers";
import Services from "@/pages/admin/Services";
import Clients from "@/pages/admin/Clients";
import Loyalty from "@/pages/admin/Loyalty";
import Plans from "@/pages/admin/Plans";
import Reports from "@/pages/admin/Reports";
import WhatsAppSettings from "@/pages/admin/WhatsAppSettings";
import PlatformLogin from "@/pages/platform/PlatformLogin";
import PlatformDashboard from "@/pages/platform/PlatformDashboard";
import PublicBooking from "@/pages/PublicBooking";

function Protected({ children, role }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-muted-foreground">
        Carregando...
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}

function RootRedirect() {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to="/dashboard" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/agendar/:slug" element={<PublicBooking />} />
      <Route path="/plataforma" element={<PlatformLogin />} />
      <Route path="/plataforma/painel" element={<PlatformDashboard />} />

      <Route element={<Protected role="admin"><Shell /></Protected>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agendamentos" element={<Appointments />} />
        <Route path="/barbeiros" element={<Barbers />} />
        <Route path="/servicos" element={<Services />} />
        <Route path="/clientes" element={<Clients />} />
        <Route path="/fidelizados" element={<Loyalty />} />
        <Route path="/planos" element={<Plans />} />
        <Route path="/relatorios" element={<Reports />} />
        <Route path="/whatsapp" element={<WhatsAppSettings />} />
      </Route>


      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}

function App() {
  useEffect(() => {
    document.documentElement.classList.remove("light");
  }, []);
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" theme="dark" richColors />
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
