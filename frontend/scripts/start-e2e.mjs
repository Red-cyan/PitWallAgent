import { cpSync, existsSync } from "node:fs";

cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
if (existsSync("public")) {
  cpSync("public", ".next/standalone/public", { recursive: true });
}
process.env.HOSTNAME = "127.0.0.1";
process.env.PORT = "3100";
await import("../.next/standalone/server.js");
