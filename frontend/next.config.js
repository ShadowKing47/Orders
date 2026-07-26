const fs = require("fs");
const path = require("path");

function loadPublicEnvFromRoot() {
  const rootEnvPath = path.join(__dirname, "..", ".env");
  const contents = fs.readFileSync(rootEnvPath, "utf-8");

  const publicEnv = {};
  for (const line of contents.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIndex = trimmed.indexOf("=");
    if (eqIndex === -1) continue;
    const key = trimmed.slice(0, eqIndex).trim();
    if (!key.startsWith("NEXT_PUBLIC_")) continue;
    publicEnv[key] = trimmed.slice(eqIndex + 1).trim();
  }
  return publicEnv;
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: loadPublicEnvFromRoot(),
};

module.exports = nextConfig;
