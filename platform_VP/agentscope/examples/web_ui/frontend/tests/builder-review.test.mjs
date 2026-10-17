import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const file = new URL('../src/pages/workforce/builder/review.ts', import.meta.url);
const code = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { canConfirm, classifierLabel } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const plan = { status: 'needs_input', agents: [], planned_agents: [{ decision: { action: 'create', reason: 'verified different' } }] };
test('an unresolved duplicate or missing operation cannot be confirmed', () => {
    assert.equal(canConfirm(plan), true);
    for (const action of ['clarify', 'repair']) assert.equal(canConfirm({ ...plan, planned_agents: [{ decision: { action } }] }), false);
    assert.equal(canConfirm({ ...plan, planned_agents: [{ ...plan.planned_agents[0], missing_tools: ['close ticket'] }] }), false);
});
test('optional knowledge permits review, required knowledge blocks it', () => {
    const entry = { ...plan.planned_agents[0], missing_knowledge: ['policy'] };
    assert.equal(canConfirm({ ...plan, planned_agents: [entry] }), true);
    assert.equal(canConfirm({ ...plan, planned_agents: [{ ...entry, knowledge_required: true }] }), false);
});
test('a generated diff goes to save and eval, not outline confirmation', () => {
    assert.equal(canConfirm({ ...plan, agents: [{ diff: [{ field: 'tools' }] }] }), false);
});
test('offline status and missing legacy judgments stay visible', () => {
    assert.match(classifierLabel(plan), /kiểm tra trùng/);
    assert.match(classifierLabel({ ...plan, classifier_status: { state: 'unavailable', model: 'jev-1.13.0', reason: 'TimeoutError' } }), /chưa thể tạo agent.*TimeoutError/);
});
