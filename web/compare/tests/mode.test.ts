import { describe, expect, it } from "vitest";

import { formatModeLabel } from "../src/mode";

describe("formatModeLabel", () => {
  it("formats wipe", () => {
    expect(formatModeLabel("wipe")).toBe("Wipe");
  });

  it("formats tile", () => {
    expect(formatModeLabel("tile")).toBe("Tile");
  });
});
