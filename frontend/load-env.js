const fs = require("fs");
const path = require("path");

const ROOT_ENV_PATH = path.join(__dirname, "..", ".env");
const OUTPUT_PATH = path.join(__dirname, ".env.local");

function parseEnvFile(contents) {
  const vars = {};
  for (const line of contents.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIndex = trimmed.indexOf("=");
    if (eqIndex === -1) continue;
    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1).trim();
    vars[key] = value;
  }
  return vars;
}

function main() {
  const rootEnv = parseEnvFile(fs.readFileSync(ROOT_ENV_PATH, "utf-8"));

  const publicVars = Object.entries(rootEnv).filter(([key]) => key.startsWith("NEXT_PUBLIC_"));

  const output = publicVars.map(([key, value]) => `${key}=${value}`).join("\n") + "\n";
  fs.writeFileSync(OUTPUT_PATH, output);
  console.log(`Wrote ${publicVars.length} NEXT_PUBLIC_* var(s) from root .env to frontend/.env.local`);
}

main();
