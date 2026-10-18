import { describe, expect, it } from "@rstest/core";

import { deliveryFileType } from "@/core/deliveries/file-type";

describe("delivery file labels", () => {
  it.each([
    ["report.MDX", "document"],
    ["notes.tex", "document"],
    ["预算.XLSX", "spreadsheet"],
    ["slides.odp", "presentation"],
    ["photo.TIFF", "image"],
    ["script.ps1", "code"],
    ["main.cpp", "code"],
    ["bundle.zip", "other"],
    [".env", "other"],
    ["README", "other"],
    ["trailing.", "other"],
  ])("labels %s as %s", (filename, category) => {
    expect(deliveryFileType(`/mnt/user-data/outputs/${filename}`)).toBe(
      category,
    );
  });

  it("does not interpret dots in a parent directory as the file extension", () => {
    expect(deliveryFileType("/mnt/user-data/outputs/source.py/README")).toBe(
      "other",
    );
  });
});
