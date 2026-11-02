import { expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const compiler = path.join(root, "skills/poteto-mode/scripts/node_modules/.bin/tsc");
const document = fs.readFileSync(path.join(root, "skills/typescript-best-practices/references/patterns.md"), "utf8");

function example(): string {
  const section = document.split("## Constructive modeling\n");
  expect(section.length).toBe(2);
  const blocks = [...section[1].split("\n## ")[0].matchAll(/```ts\n([\s\S]*?)\n```/g)]
    .map((match) => match[1])
    .filter((code) => code.includes("type NonEmpty<T>"));
  expect(blocks.length).toBe(1);
  return blocks[0];
}

function compile(source: string) {
  expect(fs.existsSync(compiler)).toBe(true);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pstack-type-example-"));
  try {
    const file = path.join(dir, "example.ts");
    fs.writeFileSync(file, source);
    return spawnSync(compiler, ["--strict", "--noUncheckedIndexedAccess", "--noEmit", "--skipLibCheck", file], { encoding: "utf8", cwd: dir });
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test("the generated nonempty example compiles with strict checked indexing", () => {
  const result = compile(example());
  expect(result.error).toBeUndefined();
  expect(result.stdout + result.stderr).toBe("");
  expect(result.status).toBe(0);
});

test("the generated tuple function rejects an empty array", () => {
  const result = compile(example() + "\nfirstEntry([]);\n");
  expect(result.status).not.toBe(0);
  expect(result.stdout + result.stderr).toContain("TS2345");
  expect(result.stdout + result.stderr).toContain("requires 1 element");
});

test("the generated functions return the first entry and guard empty plain arrays", () => {
  const source = example() + `
if (firstEntry(["first", "second"]) !== "first") throw new Error("wrong tuple entry");
if (firstEntryFromArray(["first", "second"]) !== "first") throw new Error("wrong plain entry");
let rejected = false;
try { firstEntryFromArray([]); } catch { rejected = true; }
if (!rejected) throw new Error("empty plain array was accepted");
`;
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pstack-type-runtime-"));
  try {
    const file = path.join(dir, "example.ts");
    fs.writeFileSync(file, source);
    const result = spawnSync(process.execPath, [file], { encoding: "utf8" });
    expect(result.stdout + result.stderr).toBe("");
    expect(result.status).toBe(0);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
