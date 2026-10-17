import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

import { canPresentPublishable, executionLabel, isInconclusive } from '../src/features/workforce/evaluation/presentation.ts';

test('an inconclusive result cannot be presented as publishable in a contradictory report', () => {
  for (const result of [{ passed: true, status: 'error' }, { passed: true, error: 'fixture unavailable' }]) {
    assert.equal(isInconclusive(result), true);
    assert.equal(canPresentPublishable({ publishable: true, results: [result] }), false);
  }
  assert.equal(canPresentPublishable({ publishable: true, results: [{ passed: true, status: 'passed' }] }), true);
  assert.equal(canPresentPublishable({ publishable: false, results: [] }), false);
});

test('a sandbox write is labelled separately from production reads and simulations', () => {
  assert.equal(executionLabel({ mode: 'sandbox', executed: true, consent_assumed: true }), 'Chạy thật trong sandbox');
  assert.equal(executionLabel({ mode: 'simulated', executed: false }), 'Mô phỏng, không ghi dữ liệu');
  assert.equal(executionLabel({ mode: 'read_only', executed: true }), 'Đọc thật');
  assert.equal(executionLabel({ mode: 'sandbox', executed: false }), 'Chưa thực thi trong sandbox');
  assert.equal(executionLabel({ mode: 'sandbox', executed: true, error_code: 'REVOKED' }), 'Lỗi công cụ');
});

test('pending customer fixture cleanup blocks a contradictory publishable report', () => {
  const report = { publishable: true, results: [{ passed: true, status: 'passed' }], environment: { cleanup: { status: 'pending' } } };
  assert.equal(canPresentPublishable(report), false);
  assert.equal(canPresentPublishable({ ...report, environment: { cleanup: { status: 'completed' } } }), true);
});

test('the rendered report shows assumed consent and refuses a green inconclusive case', () => {
  const require = createRequire(import.meta.url);
  const source = readFileSync(new URL('../src/components/workforce/EvaluationReport.tsx', import.meta.url), 'utf8');
  const context = { exports: {}, require: (name) => {
    if (name === '@/components/ui/badge') return { Badge: ({ children }) => React.createElement('span', null, children) };
    if (name === '@/features/workforce/evaluation/presentation') return { canPresentPublishable, executionLabel, isInconclusive };
    if (name === 'lucide-react') return { CheckCircle2: () => null, CircleAlert: () => null, Wrench: () => null };
    return require(name);
  } };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText, context);
  const report = { publishable: true, passed: 1, total: 1, ran_at: '2026-10-18T00:00:00Z', results: [{
    test_id: 'offline', scenario: 'Synthetic customer', passed: true, status: 'error', error_kind: 'environment',
    checks: [], judge: null, answer: '', tool_calls: [{ name: 'create_request', arguments: {}, mode: 'sandbox', executed: true, consent_assumed: true }],
  }] };
  const html = renderToStaticMarkup(React.createElement(context.exports.EvaluationReport, { report }));
  assert.ok(html.includes('Chạy thật trong sandbox'));
  assert.ok(html.includes('Giả định đã đồng ý trong ca thử'));
  assert.ok(html.includes('Chưa kết luận'));
  assert.ok(html.includes('0/1'));
  assert.ok(!html.includes('Đủ điều kiện phát hành'));
});
