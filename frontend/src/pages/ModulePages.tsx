import { PlaceholderPage } from "./PlaceholderPage";

export { SpritzgussPage } from "./SpritzgussPage";
export { VeredelungPage } from "./VeredelungPage";

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
