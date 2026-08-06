import { cpSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function findServerEntry(standaloneDir) {
  const direct = path.join(standaloneDir, "server.js");
  if (existsSync(direct)) return direct;
  const candidates = readdirSync(standaloneDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(standaloneDir, entry.name, "server.js"))
    .filter((entry) => existsSync(entry));
  if (candidates.length > 0) return candidates[0];
  throw new Error(`No standalone server.js found under ${standaloneDir}`);
}

const standaloneDir = path.join(process.cwd(), ".next", "standalone");
const serverEntry = findServerEntry(standaloneDir);
const appRoot = path.dirname(serverEntry);
cpSync(".next/static", path.join(appRoot, ".next/static"), { recursive: true });
if (existsSync("public")) {
  cpSync("public", path.join(appRoot, "public"), { recursive: true });
}
process.env.HOSTNAME = "127.0.0.1";
process.env.PORT = "3100";
await import(pathToFileURL(serverEntry).href);
