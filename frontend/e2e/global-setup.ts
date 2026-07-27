import { execFileSync, spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const PID_FILE = path.join(ROOT, ".playwright-server.pid");

export default async function globalSetup() {
  if (process.platform === "win32") {
    execFileSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", "npm.cmd run build"], {
      cwd: ROOT,
      stdio: "inherit",
    });
  } else {
    execFileSync("npm", ["run", "build"], { cwd: ROOT, stdio: "inherit" });
  }
  const server = spawn(process.execPath, ["scripts/start-e2e.mjs"], {
    cwd: ROOT,
    detached: true,
    stdio: "ignore",
  });
  if (!server.pid) throw new Error("Unable to start the E2E server.");
  writeFileSync(PID_FILE, String(server.pid), "utf8");
  server.unref();

  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch("http://127.0.0.1:3100");
      if (response.ok) return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
  }
  throw new Error("E2E server did not become ready within 30 seconds.");
}
