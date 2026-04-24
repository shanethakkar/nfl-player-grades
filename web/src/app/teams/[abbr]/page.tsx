type PageProps = {
  params: Promise<{ abbr: string }>;
};

export default async function TeamPage({ params }: PageProps) {
  const { abbr } = await params;
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-3xl font-bold">{abbr.toUpperCase()}</h1>
      <p className="mt-2 text-sm opacity-70">
        Roster, depth chart, and grades go here (build step 4). Roster should list
        all TEs; pure blocking TEs with &lt;15 targets have no
        <code className="mx-0.5">season_grades</code> row—surface explicitly, do
        not omit silently.
      </p>
    </main>
  );
}
