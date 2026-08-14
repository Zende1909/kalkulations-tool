import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { AppLayout } from "./components/layout/AppLayout";
import { AuthProvider } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import {
  BaugruppenPage,
  BusinessCasePage,
  InvestitionenPage,
  SpritzgussPage,
  VeredelungPage,
} from "./pages/ModulePages";
import { KundenProgrammeProjektePage } from "./pages/stammdaten/KundenProgrammeProjektePage";
import { LohnkostenPage } from "./pages/stammdaten/LohnkostenPage";
import { KaufteilePage } from "./pages/stammdaten/KaufteilePage";
import { MaschinenPage } from "./pages/stammdaten/MaschinenPage";
import { MaterialienPage } from "./pages/stammdaten/MaterialienPage";
import { ZuschlagssaetzePage } from "./pages/stammdaten/ZuschlagssaetzePage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="stammdaten/materialien" element={<MaterialienPage />} />
              <Route path="stammdaten/maschinen" element={<MaschinenPage />} />
              <Route path="stammdaten/lohnkosten" element={<LohnkostenPage />} />
              <Route path="stammdaten/kaufteile" element={<KaufteilePage />} />
              <Route path="stammdaten/zuschlagssaetze" element={<ZuschlagssaetzePage />} />
              <Route path="stammdaten/hierarchie" element={<KundenProgrammeProjektePage />} />
              <Route path="spritzguss" element={<SpritzgussPage />} />
              <Route path="veredelung" element={<VeredelungPage />} />
              <Route path="baugruppen" element={<BaugruppenPage />} />
              <Route path="investitionen" element={<InvestitionenPage />} />
              <Route path="business-case" element={<BusinessCasePage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
