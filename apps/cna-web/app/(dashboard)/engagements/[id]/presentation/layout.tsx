import { PresentationNavBar } from "./_components/nav-bar";

interface LayoutProps {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}

export default async function PresentationLayout({ children, params }: LayoutProps) {
  const { id } = await params;
  const base = `/engagements/${id}/presentation`;

  return (
    <div>
      <PresentationNavBar base={base} />
      {children}
    </div>
  );
}
