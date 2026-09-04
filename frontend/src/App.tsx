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
  MaschinenauslastungPage,
  SpritzgussPage,
  VeredelungPage,
} from "./pages/ModulePages";
import { KundenProgrammeProjektePage } from "./pages/stammdaten/KundenProgrammeProjektePage";
import { LaenderPage } from "./pages/stammdaten/LaenderPage";
import { LohnkostenPage } from "./pages/stammdaten/LohnkostenPage";
import { KaufteilePage } from "./pages/stammdaten/KaufteilePage";
import { MaschinenPage } from "./pages/stammdaten/MaschinenPage";
import { MaterialgruppenPage } from "./pages/stammdaten/MaterialgruppenPage";
import { MaterialienPage } from "./pages/stammdaten/MaterialienPage";
import { WerkePage } from "./pages/stammdaten/WerkePage";
import { WerkZuschlaegePage } from "./pages/stammdaten/WerkZuschlaegePage";
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
              <Route path="stammdaten/materialgruppen" element={<MaterialgruppenPage />} />
              <Route path="stammdaten/materialien" element={<MaterialienPage />} />
              <Route path="stammdaten/laender" element={<LaenderPage />} />
              <Route path="stammdaten/werke" element={<WerkePage />} />
              <Route path="stammdaten/werk-zuschlaege" element={<WerkZuschlaegePage />} />
              <Route path="stammdaten/maschinen" element={<MaschinenPage />} />
              <Route path="stammdaten/lohnkosten" element={<LohnkostenPage />} />
              <Route path="stammdaten/kaufteile" element={<KaufteilePage />} />
              <Route path="stammdaten/zuschlagssaetze" element={<ZuschlagssaetzePage />} />
              <Route path="stammdaten/hierarchie" element={<KundenProgrammeProjektePage />} />
              <Route path="spritzguss" element={<SpritzgussPage />} />
              <Route path="veredelung" element={<VeredelungPage />} />
              <Route path="baugruppen" element={<BaugruppenPage />} />
              <Route path="baugruppen/familien" element={<Navigate to="/baugruppen" replace />} />
              <Route path="maschinenauslastung" element={<MaschinenauslastungPage />} />
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
