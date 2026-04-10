import { auth, signOut } from "@/lib/auth";
import { redirect } from "next/navigation";
import Link from "next/link";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user) redirect("/auth/signin");

  const email = session.user.email ?? "";
  const initial = email.charAt(0).toUpperCase();

  return (
    <div className="flex min-h-screen flex-col">
      {/* ── Glass header ── */}
      <header className="header-glass sticky top-0 z-50">
        <div className="mx-auto flex max-w-screen-2xl items-center justify-between px-6 py-3">
          {/* Logo + wordmark */}
          <Link href="/dashboard" className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/cbts_light.png"
              alt="CBTS"
              className="h-8 w-auto dark:hidden"
            />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/cbts_dark.png"
              alt="CBTS"
              className="h-8 w-auto hidden dark:block"
            />
            <div className="mx-1 h-5 w-px bg-navy-100 dark:bg-navy-700" />
            <span className="hidden text-sm font-semibold tracking-tight text-navy-500 dark:text-navy-200 sm:block">
              Cloud Network Assessment
            </span>
          </Link>

          {/* User controls */}
          <div className="flex items-center gap-3">
            {/* Avatar + email */}
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-100 ring-2 ring-teal-500/25 dark:bg-teal-900">
                <span className="text-xs font-bold text-teal-700 dark:text-teal-300">
                  {initial}
                </span>
              </div>
              <span className="hidden text-sm font-medium text-navy-500 dark:text-navy-200 md:block">
                {email}
              </span>
            </div>

            {/* Sign out */}
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/auth/signin" });
              }}
            >
              <button
                type="submit"
                className="rounded-lg border border-navy-100 bg-white/60 px-3.5 py-1.5 text-xs font-semibold text-navy-600 transition-colors hover:bg-white/90 dark:border-navy-700 dark:bg-white/5 dark:text-navy-200 dark:hover:bg-white/10"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      {/* ── Page content ── */}
      <main className="mx-auto w-full max-w-screen-2xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
