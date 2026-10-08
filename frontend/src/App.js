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
import Clients from "@/pages/admin/Clients";
import Loyalty from "@/pages/admin/Loyalty";
import Plans from "@/pages/admin/Plans";
import Reports from "@/pages/admin/Reports";
import Booking from "@/pages/client/Booking";
import MyAppointments from "@/pages/client/MyAppointments";
import ClientPlans from "@/pages/client/ClientPlans";
import ClientLoyalty from "@/pages/client/ClientLoyalty";

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
    return <Navigate to={user.role === "admin" ? "/dashboard" : "/agendar"} replace />;
  }
  return children;
}

function RootRedirect() {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/dashboard" : "/agendar"} replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<Login />} />

      <Route element={<Protected role="admin"><Shell /></Protected>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agendamentos" element={<Appointments />} />
        <Route path="/barbeiros" element={<Barbers />} />
        <Route path="/clientes" element={<Clients />} />
        <Route path="/fidelizados" element={<Loyalty />} />
        <Route path="/planos" element={<Plans />} />
        <Route path="/relatorios" element={<Reports />} />
      </Route>

      <Route element={<Protected role="client"><Shell /></Protected>}>
        <Route path="/agendar" element={<Booking />} />
        <Route path="/meus-agendamentos" element={<MyAppointments />} />
        <Route path="/planos-cliente" element={<ClientPlans />} />
        <Route path="/fidelidade" element={<ClientLoyalty />} />
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
