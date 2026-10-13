"use strict";

const fs = require("node:fs");
const ts = require(process.argv[2]);
const cases = JSON.parse(fs.readFileSync(0, "utf8"));

function inspect(fixture) {
  const source = ts.createSourceFile("fixture.ts", fixture.source, ts.ScriptTarget.Latest, true);
  const owners = new Set();
  const statements = new Map();
  const collisions = [];
  function visit(node, scope) {
    let childScope = scope;
    if (ts.isClassDeclaration(node) && node.name) {
      childScope = [...scope, node.name.text];
      if (node.members.some(member => ts.isPropertyDeclaration(member) && member.initializer
          && member.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.StaticKeyword))) {
        owners.add(childScope.join("."));
      }
    }
    if (ts.isFunctionLike(node) && node.body) {
      const name = ts.isConstructorDeclaration(node) ? scope.at(-1)
        : node.name ? node.name.getText(source) : "<lambda>";
      const owner = ts.isConstructorDeclaration(node) ? scope.join(".") : [...scope, name].join(".");
      owners.add(owner);
      childScope = [...scope, name];
    }
    if (ts.isStatement(node) && !ts.isBlock(node) && !ts.isFunctionDeclaration(node)
        && !ts.isClassDeclaration(node) && !ts.isEmptyStatement(node)) {
      const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
      if (statements.has(line)) collisions.push(line);
      statements.set(line, node.kind);
    }
    ts.forEachChild(node, child => visit(child, childScope));
  }
  visit(source, []);
  return {
    id: fixture.id, owners: [...owners], statement_collisions: collisions,
    parse_errors: source.parseDiagnostics.map(error => ts.flattenDiagnosticMessageText(error.messageText, " ")),
  };
}

process.stdout.write(JSON.stringify(cases.map(inspect)));
