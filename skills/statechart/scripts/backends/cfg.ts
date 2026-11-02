import { CHART_STATES, type ConfigSection, RERUN_STATES, type Spec } from "../ir.ts";

export function configText(sections: ConfigSection[], extra: string[]) {
  const lines: string[] = [];
  for (const s of sections) lines.push(`${s.key} ${s.tokens.join(" ")}`);
  lines.push(...extra);
  return lines.join("\n");
}

export function generatedNames(reserved: Iterable<string>) {
  const used = new Set(reserved);
  const fresh = (base: string) => {
    let name = base;
    for (let suffix = 1; used.has(name); suffix++) name = `${base}${suffix}`;
    used.add(name);
    return name;
  };
  return {
    bound: fresh("ChartBound"),
    chart: fresh("ChartRun"),
    tlc: fresh("ChartTLC"),
    naturals: fresh("ChartNaturals"),
    budget: fresh("ChartBudget"),
    broken: fresh("ChartBroken"),
    mark: fresh("ChartMark"),
  };
}

type GeneratedNames = ReturnType<typeof generatedNames>;

export const boundRun = (module: string, names: GeneratedNames) =>
  [
    `---- MODULE ${names.bound} ----`,
    `EXTENDS ${module}`,
    `${names.tlc} == INSTANCE TLC`,
    `${names.naturals} == INSTANCE Naturals`,
    `${names.bound} == ${names.naturals}!<(${names.tlc}!TLCGet("distinct"), ${RERUN_STATES})`,
    `====`,
  ].join("\n");

export function chartRun({ module, variables, invariants }: Spec, tag: string, names: GeneratedNames) {
  const every: string[] = [];
  for (const name of invariants) every.push(`(IF ~${name} THEN {"${name}"} ELSE {}) \\cup `);
  return [
    `---- MODULE ${names.chart} ----`,
    `EXTENDS ${module}`,
    `${names.tlc} == INSTANCE TLC`,
    `${names.naturals} == INSTANCE Naturals`,
    `${names.budget} == ${names.naturals}!<=(${names.tlc}!TLCGet("distinct"), ${CHART_STATES})`,
    `${names.broken} == ${every.join("")}{}`,
    `${names.mark} == ${names.broken} = {} \\/ ${names.tlc}!PrintT(<<"${tag}", <<${variables.join(", ")}>>, ${names.broken}>>)`,
    `====`,
  ].join("\n");
}
