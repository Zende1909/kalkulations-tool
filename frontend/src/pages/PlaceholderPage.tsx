interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
      <p className="mt-2 text-gray-600">{description}</p>
      <div className="mt-8 rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
        <p className="text-gray-500">Dieses Modul wird in einer späteren Iteration implementiert.</p>
      </div>
    </div>
  );
}
