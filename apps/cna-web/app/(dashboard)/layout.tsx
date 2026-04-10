import { auth, signOut } from "@/lib/auth";
import { redirect } from "next/navigation";

// All routes under (dashboard)/ require an active session.
// Unauthenticated requests are sent to the sign-in page.
export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/auth/signin");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold text-gray-900">
            CNA Platform
          </span>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{session.user.email}</span>
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/auth/signin" });
              }}
            >
              <button
                type="submit"
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
