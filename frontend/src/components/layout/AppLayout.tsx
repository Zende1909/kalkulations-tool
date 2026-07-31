import { Outlet } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
          <div>
            <p className="text-sm text-gray-500">Angemeldet als</p>
            <p className="font-medium text-gray-900">{user?.email}</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium uppercase text-slate-700">
              {user?.role}
            </span>
            <button
              type="button"
              onClick={logout}
              className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Abmelden
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
