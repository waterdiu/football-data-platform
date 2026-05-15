import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');
const worldCupSiteRoot = path.resolve(rootDir, '..', 'worldcup', '2026');

const apiFootballMatchesPath = path.join(worldCupSiteRoot, 'src', 'data', 'apiFootballQualifierMatches.ts');
const qualifierMatchesPath = path.join(worldCupSiteRoot, 'src', 'data', 'qualifierMatches.ts');
const outputPath = path.join(rootDir, 'data', 'public', 'qualifier-matches.json');
const reportPath = path.join(rootDir, 'reports', 'qualifier_matches_import_report.json');

function extractArrayLiteral(source, declarationPrefix) {
  const start = source.indexOf(declarationPrefix);
  if (start < 0) {
    throw new Error(`Declaration not found: ${declarationPrefix}`);
  }
  const assignmentStart = source.indexOf('=', start);
  if (assignmentStart < 0) {
    throw new Error(`Assignment not found for: ${declarationPrefix}`);
  }
  const arrayStart = source.indexOf('[', assignmentStart);
  if (arrayStart < 0) {
    throw new Error(`Array start not found for: ${declarationPrefix}`);
  }

  let depth = 0;
  let inString = false;
  let stringQuote = '';
  let escaped = false;

  for (let index = arrayStart; index < source.length; index += 1) {
    const char = source[index];

    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === stringQuote) {
        inString = false;
        stringQuote = '';
      }
      continue;
    }

    if (char === '"' || char === "'" || char === '`') {
      inString = true;
      stringQuote = char;
      continue;
    }

    if (char === '[') {
      depth += 1;
    } else if (char === ']') {
      depth -= 1;
      if (depth === 0) {
        return source.slice(arrayStart, index + 1);
      }
    }
  }

  throw new Error(`Array literal not terminated for: ${declarationPrefix}`);
}

function evaluateArrayLiteral(arrayLiteral, context = {}) {
  return vm.runInNewContext(arrayLiteral, context, { timeout: 1000 });
}

function mergeQualifierMatches(manualMatches, importedMatches) {
  const seen = new Set();
  return [...manualMatches, ...importedMatches].filter((match) => {
    const key = [
      match.confederationId,
      match.dateLabel,
      String(match.homeTeam).toLowerCase(),
      String(match.awayTeam).toLowerCase(),
    ].join('|');

    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function writeJson(filePath, payload) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

async function main() {
  const apiFootballSource = await fs.readFile(apiFootballMatchesPath, 'utf8');
  const qualifierSource = await fs.readFile(qualifierMatchesPath, 'utf8');

  const apiFootballArray = extractArrayLiteral(
    apiFootballSource,
    'export const apiFootballQualifierMatches: QualifierMatchData[] ='
  );
  const manualArray = extractArrayLiteral(
    qualifierSource,
    'const manualQualifierMatches: QualifierMatchData[] ='
  );

  const importedMatches = evaluateArrayLiteral(apiFootballArray);
  const manualMatches = evaluateArrayLiteral(manualArray, {
    unavailable: ['阵容', '比赛统计', '换人', '红黄牌', '球员赛后评分'],
    noRatings: ['球员赛后评分'],
  });
  const qualifierMatches = mergeQualifierMatches(manualMatches, importedMatches);

  const report = {
    generated_at: '2026-05-15T00:00:00Z',
    source_files: [apiFootballMatchesPath, qualifierMatchesPath],
    imported_api_football_matches: importedMatches.length,
    imported_manual_matches: manualMatches.length,
    merged_match_count: qualifierMatches.length,
  };

  await writeJson(outputPath, qualifierMatches);
  await writeJson(reportPath, report);

  console.log(`Published ${qualifierMatches.length} qualifier matches to ${outputPath}`);
  console.log(`Wrote qualifier import report to ${reportPath}`);
}

await main();
