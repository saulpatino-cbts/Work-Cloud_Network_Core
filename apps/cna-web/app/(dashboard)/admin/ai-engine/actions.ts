"use server";

import { revalidatePath } from "next/cache";

import { auth } from "@/lib/auth";
import { normalizeAiEngine, setActiveAiEngine } from "@/lib/ai-engine";

export async function setAiEngineAction(formData: FormData): Promise<void> {
  const session = await auth();
  if (!session?.user) {
    throw new Error("Authentication required.");
  }

  if (session.user.role !== "ADMIN") {
    throw new Error("Only admins can switch the active AI engine.");
  }

  const engine = normalizeAiEngine(formData.get("engine")?.toString());
  if (!engine) {
    throw new Error("Invalid AI engine.");
  }

  await setActiveAiEngine(engine, session.user.id);
  revalidatePath("/admin/ai-engine");
}
