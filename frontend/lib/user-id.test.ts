import { describe, expect, it } from "vitest";

import { getUserId } from "@/lib/user-id";

function makeStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, String(value)),
  };
}

describe("getUserId", () => {
  it("generates and persists a stable anonymous id", () => {
    const storage = makeStorage();
    const first = getUserId(storage);
    const second = getUserId(storage);
    expect(first).toBeTruthy();
    expect(second).toBe(first);
  });

  it("reuses an existing id across calls", () => {
    const storage = makeStorage();
    storage.setItem("pitwall.user_id", "fixed-user");
    expect(getUserId(storage)).toBe("fixed-user");
  });

  it("returns empty string without storage", () => {
    expect(getUserId(null)).toBe("");
  });
});
