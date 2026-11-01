export interface RecipeInput { role: string; label: string; accept: string[]; required: boolean; multiple?: boolean }
export interface RecipeOption { name: string; label: string; kind: "text" | "select"; options?: string[]; default?: string; required?: boolean }
export interface Recipe {
  id: string; name: string; icon: string; pitch: string; inputs: RecipeInput[]; options: RecipeOption[];
  outputs: string[]; engines: { id: string; label: string }[]; prompts: { name: string; available: boolean }[];
}
export interface Suggestion { id: string; name: string; score: number; why: string | null }

/** Guess which input role an uploaded file fills, from its name. */
export function guessRole(recipe: Recipe, filename: string): string | null {
  const n = filename.toLowerCase();
  const ext = "." + (n.split(".").pop() ?? "");
  const fits = recipe.inputs.filter((i) => i.accept.includes(ext));
  if (!fits.length) return null;
  const by = (re: RegExp, role: string) => (re.test(n) && fits.some((i) => i.role === role) ? role : null);
  return by(/comment|reviewer|response|decision|rebuttal/, "comments")
    ?? by(/reference|template|sample|style|example/, "reference")
    ?? by(/template|\.cls$|\.sty$/, "template")
    ?? fits[0].role;
}
