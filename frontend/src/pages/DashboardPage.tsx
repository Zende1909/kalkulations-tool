const modules = [
  { title: "Stammdaten", description: "Materialien, Maschinen, Lohnkosten und Zuschlagssätze verwalten" },
  { title: "Spritzguss-Kalkulation", description: "Kalkulation von Spritzgussteilen" },
  { title: "Veredelung", description: "Nachbearbeitungs- und Veredelungskosten" },
  { title: "Baugruppen", description: "Zusammenführung mehrerer Teile" },
  { title: "Investitionen", description: "Werkzeug- und Anlageninvestitionen" },
];

export function DashboardPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
      <p className="mt-2 text-gray-600">
        Willkommen im Kalkulationstool für Kunststoffmodule in der Automotive-Zulieferindustrie.
      </p>

      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {modules.map((module) => (
          <div key={module.title} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="font-semibold text-gray-900">{module.title}</h3>
            <p className="mt-2 text-sm text-gray-600">{module.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
