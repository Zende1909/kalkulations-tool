import { PlaceholderPage } from "./PlaceholderPage";

export { SpritzgussPage } from "./SpritzgussPage";

export function VeredelungPage() {
  return (
    <PlaceholderPage
      title="Veredelung"
      description="Kalkulation von Veredelungs- und Nachbearbeitungsprozessen."
    />
  );
}

export function BaugruppenPage() {
  return (
    <PlaceholderPage
      title="Baugruppen"
      description="Zusammenführung und Kalkulation von Baugruppen aus mehreren Einzelteilen."
    />
  );
}

export function InvestitionenPage() {
  return (
    <PlaceholderPage
      title="Investitionen"
      description="Planung und Kalkulation von Werkzeug- und Anlageninvestitionen."
    />
  );
}
