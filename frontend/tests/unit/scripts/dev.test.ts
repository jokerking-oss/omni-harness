import { describe, expect, test } from "@rstest/core";

import { getDevBundler, getNextDevArgs } from "../../../scripts/dev.mjs";

describe("frontend dev launcher", () => {
  test("allows an explicit bundler override on every platform", () => {
    expect(getDevBundler("win32", { OMNI_HARNESS_DEV_BUNDLER: "turbo" })).toBe(
      "turbo",
    );
    expect(
      getNextDevArgs("linux", [], { OMNI_HARNESS_DEV_BUNDLER: "webpack" }),
    ).toEqual(["dev", "--webpack"]);
  });

  test("rejects an unsupported bundler override", () => {
    expect(() =>
      getDevBundler("linux", { OMNI_HARNESS_DEV_BUNDLER: "invalid" }),
    ).toThrow('OMNI_HARNESS_DEV_BUNDLER must be either "turbo" or "webpack"');
  });

  test("passes through extra Next.js arguments", () => {
    expect(getNextDevArgs("win32", ["--", "--port", "3302"])).toEqual([
      "dev",
      "--webpack",
      "--port",
      "3302",
    ]);
  });

  test("uses webpack by default on every platform", () => {
    expect(getDevBundler("win32")).toBe("webpack");
    expect(getDevBundler("linux")).toBe("webpack");
    expect(getDevBundler("darwin")).toBe("webpack");
    expect(getNextDevArgs("win32")).toEqual(["dev", "--webpack"]);
    expect(getNextDevArgs("linux")).toEqual(["dev", "--webpack"]);
  });
});
