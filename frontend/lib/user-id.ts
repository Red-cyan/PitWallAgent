/**
 * 匿名用户身份。
 *
 * 项目暂无登录体系，为了后端长期画像能按用户隔离（user_id 维度持久化），
 * 在浏览器本地生成并持久化一个匿名 user_id；同一浏览器始终复用同一身份。
 */

const STORAGE_KEY = "pitwall.user_id";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

function defaultStorage(): StorageLike | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  return window.localStorage;
}

export function getUserId(storage: StorageLike | null = defaultStorage()): string {
  if (!storage) return "";
  const existing = storage.getItem(STORAGE_KEY);
  if (existing) return existing;
  const generated = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `anon-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  storage.setItem(STORAGE_KEY, generated);
  return generated;
}
