import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const roots = ['server', 'shared', 'app', 'domain-tools'];
const normalize = (value) => value.replaceAll('\\', '/');
const inside = (file, directory) => file === directory || file.startsWith(`${directory}/`);
const databasePackages = /^(pg|postgres|postgresql|drizzle-orm|prisma|@prisma\/client|@qdrant\/[^/]+)(\/|$)/;

/** Paths are repo-relative and resolved before applying these rules. */
export function dependencyViolation(from, to) {
  from = normalize(from);
  to = normalize(to);
  const inAny = (...directories) => directories.some((directory) => inside(to, directory));

  if (inside(from, 'shared/platform') && !inside(to, 'shared/platform')) {
    return 'Shared platform contracts must remain domain/framework independent';
  }
  const sharedDomain = from.match(/^shared\/domains\/([^/]+)\//)?.[1];
  if (sharedDomain && !inAny('shared/platform', `shared/domains/${sharedDomain}`)) {
    return 'Shared domain contracts may depend only on their own contracts and platform contracts';
  }
  if (inside(from, 'server/src/platform') && !inAny('server/src/platform', 'shared/platform', 'server/src/db/schema/platform')) {
    return 'Platform must use DomainAdapter instead of concrete domain imports';
  }
  const domain = from.match(/^server\/src\/domains\/([^/]+)\//)?.[1];
  if (domain && !inAny(`server/src/domains/${domain}`, `shared/domains/${domain}`, 'shared/platform', `server/src/db/schema/domains/${domain}`)) {
    return 'Domain must use contracts/injected ports instead of another module implementation';
  }
  if (inside(from, 'server/src/db/schema/platform') && !inAny('server/src/db/schema/platform', 'shared/platform')) {
    return 'Platform schema must not depend on domain schemas';
  }
  const schemaDomain = from.match(/^server\/src\/db\/schema\/domains\/([^/]+)\//)?.[1];
  if (schemaDomain && !inAny(`server/src/db/schema/domains/${schemaDomain}`, `shared/domains/${schemaDomain}`, 'shared/platform', 'server/src/db/schema/platform/identity.ts')) {
    return 'Domain schema may reference only its own schema and shared identity';
  }
  if (inside(from, 'app') && !inAny('app', 'shared')) {
    return 'UI must call APIs instead of importing backend implementations';
  }
  if (inside(from, 'app/src/features/platform') && inAny('app/src/features/domains', 'shared/domains')) {
    return 'Platform UI must remain domain independent';
  }
  const uiDomain = from.match(/^app\/src\/features\/domains\/([^/]+)\//)?.[1];
  const targetUiDomain = to.match(/^(?:app\/src\/features|shared)\/domains\/([^/]+)\//)?.[1];
  if (uiDomain && targetUiDomain && uiDomain !== targetUiDomain) {
    return 'Domain UI must not depend on another domain';
  }
  if (inside(from, 'domain-tools/shared') && !inAny('domain-tools/shared', 'shared/platform')) {
    return 'Shared MCP helpers must remain domain independent';
  }
  const toolDomain = from.match(/^domain-tools\/([^/]+)\//)?.[1];
  if (toolDomain && toolDomain !== 'shared' && !inAny(`domain-tools/${toolDomain}`, 'domain-tools/shared', 'shared/platform', `shared/domains/${toolDomain}`)) {
    return 'MCP uses service APIs/contracts, never server or database modules';
  }
  return null;
}

export function externalViolation(from, specifier) {
  if (inside(from, 'shared')) return 'Shared contracts cannot import external runtime/framework packages';
  if ((inside(from, 'domain-tools') || inside(from, 'app')) && databasePackages.test(specifier)) {
    return 'UI/MCP must not access PostgreSQL or Qdrant directly';
  }
  if (/agentscope/i.test(specifier)) return 'AgentScope belongs behind the Python RuntimeAdapter';
  return null;
}

export function importSpecifiers(source) {
  const result = [];
  const file = ts.createSourceFile('source.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  function visit(node) {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) {
      result.push(ts.isStringLiteralLike(node.moduleSpecifier) ? node.moduleSpecifier.text : null);
    }
    if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
      const expression = node.moduleReference.expression;
      result.push(expression && ts.isStringLiteralLike(expression) ? expression.text : null);
    }
    if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument) && ts.isStringLiteralLike(node.argument.literal)) {
      result.push(node.argument.literal.text);
    }
    if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
      (ts.isIdentifier(node.expression) && node.expression.text === 'require'))) {
      const argument = node.arguments[0];
      result.push(argument && ts.isStringLiteralLike(argument) ? argument.text : null);
    }
    ts.forEachChild(node, visit);
  }
  visit(file);
  return result;
}

function* sourceFiles(directory) {
  if (!fs.existsSync(directory)) return;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (['node_modules', 'dist', '__pycache__'].includes(entry.name)) continue;
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* sourceFiles(target);
    else if (/\.(?:[cm]?[jt]sx?)$/.test(entry.name)) yield target;
  }
}

export function checkArchitecture(repo = process.cwd()) {
  const config = ts.readConfigFile(path.join(repo, 'tsconfig.json'), ts.sys.readFile);
  if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
  const { options } = ts.parseJsonConfigFileContent(config.config, ts.sys, repo);
  const errors = [];
  for (const root of roots) {
    for (const file of sourceFiles(path.join(repo, root))) {
      const from = normalize(path.relative(repo, file));
      for (const specifier of importSpecifiers(fs.readFileSync(file, 'utf8'))) {
        if (specifier === null) {
          errors.push(`${from}: computed module imports require an explicit static boundary`);
          continue;
        }
        const resolved = ts.resolveModuleName(specifier, file, options, ts.sys).resolvedModule;
        let error;
        if (resolved && !resolved.isExternalLibraryImport) {
          error = dependencyViolation(from, normalize(path.relative(repo, resolved.resolvedFileName)));
        } else if (specifier.startsWith('.') || specifier.startsWith('/') || specifier.startsWith('#')) {
          error = 'Unresolved local import';
        } else {
          error = externalViolation(from, specifier);
          if (!error && !resolved && !specifier.startsWith('node:')) error = 'Unresolved package or alias';
        }
        if (error) errors.push(`${from} -> ${specifier}: ${error}`);
      }
    }
  }
  return errors;
}

if (import.meta.url === pathToFileURL(path.resolve(process.argv[1] ?? '')).href) {
  const errors = checkArchitecture();
  if (errors.length) {
    console.error(errors.join('\n'));
    process.exitCode = 1;
  } else {
    console.log('Architecture imports: OK');
  }
}
