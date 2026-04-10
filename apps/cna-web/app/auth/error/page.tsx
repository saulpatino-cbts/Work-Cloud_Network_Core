import { type NextSearchParams } from "next/dist/server/request/search-params";

// Auth.js v5 redirects here when authentication fails.
// The `error` query param contains the error code (e.g. "OAuthSignin",
// "OAuthCallback", "OAuthCreateAccount", "Callback", "OAuthAccountNotLinked",
// "EmailCreateAccount", "CredentialsSignin", "SessionRequired").
const AUTH_ERROR_MESSAGES: Record<string, string> = {
  OAuthSignin: "Could not initiate sign-in with Microsoft. Please try again.",
  OAuthCallback: "Microsoft returned an error during sign-in. Please try again.",
  OAuthCreateAccount: "Could not create your account. Contact your administrator.",
  OAuthAccountNotLinked:
    "This Microsoft account is already linked to a different user.",
  Callback: "An error occurred during sign-in callback.",
  SessionRequired: "You must be signed in to access this page.",
  Default: "An authentication error occurred.",
};

export default async function AuthErrorPage({
  searchParams,
}: {
  searchParams: NextSearchParams;
}) {
  const params = await searchParams;
  const error = typeof params.error === "string" ? params.error : "Default";
  const message = AUTH_ERROR_MESSAGES[error] ?? AUTH_ERROR_MESSAGES.Default;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-2 text-2xl font-semibold tracking-tight text-gray-900">
          Sign-in failed
        </h1>
        <p className="mb-6 text-sm text-gray-500">{message}</p>
        {process.env.NODE_ENV !== "production" && (
          <p className="mb-4 rounded bg-gray-100 p-2 font-mono text-xs text-gray-600">
            error: {error}
          </p>
        )}
        <a
          href="/auth/signin"
          className="block w-full rounded-lg bg-blue-600 px-4 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-700"
        >
          Try again
        </a>
      </div>
    </div>
  );
}
