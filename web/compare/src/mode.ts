export type CompareMode = "wipe" | "tile";

export function formatModeLabel(mode: CompareMode): string {
  if (mode === "wipe") {
    return "Wipe";
  }
  return "Tile";
}
