import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const worldCupSiteRoot = path.resolve(rootDir, '..', 'worldcup', '2026');
const siteDataDir = path.resolve(rootDir, '..', 'worldcup', '2026', 'src', 'data');
const publicDir = path.join(rootDir, 'data', 'public');
const reportsDir = path.join(rootDir, 'reports');
const typescriptModulePath = path.join(worldCupSiteRoot, 'node_modules', 'typescript', 'lib', 'typescript.js');

function stripImports(source) {
  return source
    .replace(/^import\s+type\s+[^;]+;\n/gm, '')
    .replace(/^import\s+\{[^;]+\}\s+from\s+['"][^'"]+['"];\n/gm, '')
    .replace(/^import\s+[^;]+\s+from\s+['"][^'"]+['"];\n/gm, '');
}

async function transpileTs(source) {
  const ts = await import(typescriptModulePath);
  const result = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020
    }
  });
  return result.outputText;
}

async function evaluateTsModule(source, exportNames, injected = {}) {
  let code = stripImports(source);
  for (const exportName of exportNames) {
    code = code.replace(
      new RegExp(`export const ${exportName}(?:\\s*:[^=]+)?\\s*=`, 'g'),
      `const ${exportName} =`
    );
  }
  code = await transpileTs(code);
  code += `\nmodule.exports = { ${exportNames.join(', ')} };`;

  const context = vm.createContext({
    module: { exports: {} },
    exports: {},
    console,
    ...injected
  });
  const script = new vm.Script(code, { timeout: 1000 });
  script.runInContext(context);
  return context.module.exports;
}

async function loadModule(fileName, exportNames, injected = {}) {
  const filePath = path.join(siteDataDir, fileName);
  const source = await fs.readFile(filePath, 'utf8');
  return evaluateTsModule(source, exportNames, injected);
}

async function writeJson(filePath, payload) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

async function main() {
  const { groupFixtures } = await loadModule('groupFixtures.ts', ['groupFixtures']);
  const { groups } = await loadModule('groups.ts', ['groups']);
  const { groupStageMatches } = await loadModule('groupStageMatches.ts', ['groupStageMatches'], {
    groupFixtures,
    groups
  });
  const { bracket } = await loadModule('bracket.ts', ['bracket']);
  const { fullSchedule } = await loadModule('fullSchedule.ts', ['fullSchedule']);
  const { finalsMatchResults } = await loadModule('finalsMatchResults.ts', ['finalsMatchResults'], {
    bracket,
    groupStageMatches
  });
  const { finalsDataCoverage } = await loadModule('finalsDataCoverage.ts', ['finalsDataCoverage']);
  const { apiFootballQualifierMatches } = await loadModule('apiFootballQualifierMatches.ts', ['apiFootballQualifierMatches']);
  const { qualifierMatches, qualifierMissingDataReport, apiFootballQualifierSourceReports } = await loadModule(
    'qualifierMatches.ts',
    ['qualifierMatches', 'qualifierMissingDataReport', 'apiFootballQualifierSourceReports'],
    { apiFootballQualifierMatches }
  );

  const outputs = {
    'worldcup-site-groups.json': groups,
    'worldcup-site-group-fixtures.json': groupFixtures,
    'worldcup-site-group-stage-matches.json': groupStageMatches,
    'worldcup-site-bracket.json': bracket,
    'worldcup-site-full-schedule.json': fullSchedule,
    'worldcup-site-finals-results.json': finalsMatchResults,
    'worldcup-site-finals-coverage.json': finalsDataCoverage,
    'worldcup-site-qualifier-matches.json': qualifierMatches,
    'worldcup-site-qualifier-missing-data.json': qualifierMissingDataReport,
    'worldcup-site-qualifier-source-reports.json': apiFootballQualifierSourceReports
  };

  await Promise.all(
    Object.entries(outputs).map(([fileName, payload]) => writeJson(path.join(publicDir, fileName), payload))
  );

  const report = {
    generated_at: '2026-05-15T00:00:00Z',
    source_dir: siteDataDir,
    datasets: Object.fromEntries(
      Object.entries(outputs).map(([fileName, payload]) => [fileName, Array.isArray(payload) ? payload.length : 1])
    )
  };
  await writeJson(path.join(reportsDir, 'worldcup_site_local_import_report.json'), report);

  console.log(`Imported ${groupFixtures.length} group fixtures from worldcup/2026`);
  console.log(`Imported ${groupStageMatches.length} group-stage matches from worldcup/2026`);
  console.log(`Imported ${finalsMatchResults.length} finals result rows from worldcup/2026`);
  console.log(`Imported ${qualifierMatches.length} qualifier rows from worldcup/2026`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
