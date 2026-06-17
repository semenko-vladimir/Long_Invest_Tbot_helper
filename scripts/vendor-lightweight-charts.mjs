import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const source = join(
  root,
  "node_modules",
  "lightweight-charts",
  "dist",
  "lightweight-charts.standalone.production.js",
);
const targetDir = join(root, "app", "backend", "web", "static", "vendor");
const target = join(targetDir, "lightweight-charts.standalone.production.js");

mkdirSync(targetDir, { recursive: true });
copyFileSync(source, target);
console.log(`Copied ${source} -> ${target}`);
