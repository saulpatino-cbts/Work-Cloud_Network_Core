import { signIn } from "@/lib/auth";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-2 text-2xl font-semibold tracking-tight text-gray-900">
          CNA Platform
        </h1>
        <p className="mb-8 text-sm text-gray-500">
          Sign in with your CBTS Microsoft account to continue.
        </p>
        <form
          action={async () => {
            "use server";
            await signIn("microsoft-entra-id");
          }}
        >
          <button
            type="submit"
            className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Sign in with Microsoft
          </button>
        </form>
      </div>
    </div>
  );
}
