import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';
import { UserMsg } from '@agentscope-ai/agentscope/message';

const source = ts.transpileModule(readFileSync(new URL('../src/lib/crypto.ts', import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;

test('HTTP context: reproduces message failure, then creates SDK messages and unique UUID v4 IDs', () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  const crypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) };
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: crypto });
  try {
    assert.throws(() => UserMsg({ name: 'user', content: 'hello' }), /randomUUID/);
    vm.runInNewContext(source, { crypto, Uint8Array });
    const ids = new Set();
    for (let i = 0; i < 1000; i++) {
      const msg = UserMsg({ name: 'user', content: [{ id: crypto.randomUUID(), type: 'text', text: 'hello' }] });
      assert.match(msg.id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      ids.add(msg.id);
    }
    assert.equal(ids.size, 1000);
  } finally {
    Object.defineProperty(globalThis, 'crypto', descriptor);
  }
});

test('HTTPS context: preserves native randomUUID', () => {
  const native = () => 'native';
  const crypto = { randomUUID: native };
  vm.runInNewContext(source, { crypto });
  assert.equal(crypto.randomUUID, native);
});

test('HTTP context: actual TextInput send button delivers text to the SDK callback', async () => {
  const { createRequire } = await import('node:module');
  const require = createRequire(import.meta.url);
  const crypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) };
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: crypto });
  try {
    vm.runInNewContext(source, { crypto, Uint8Array });
    let stateIndex = 0;
    const react = {
      forwardRef: (fn) => fn,
      useState: (initial) => [stateIndex++ === 0 ? 'local send test' : initial, () => {}],
      useRef: () => ({ current: null }), useMemo: (fn) => fn(),
      useLayoutEffect() {}, useImperativeHandle() {},
    };
    const mocks = new Proxy({
      react: { __esModule: true, default: react, ...react },
      'react/jsx-runtime': require('react/jsx-runtime'),
      '@/lib/utils': { cn: () => '' },
      '@/i18n/useI18n.ts': { useTranslation: () => ({ t: (key) => key }) },
    }, { get: (target, id) => target[id] ?? new Proxy({}, { get: (_, name) => name }) });
    const context = { exports: {}, require: (id) => mocks[id], crypto };
    const inputSource = readFileSync(new URL('../src/components/chat/TextInput.tsx', import.meta.url), 'utf8');
    vm.runInNewContext(ts.transpileModule(inputSource, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText, context);
    let sent;
    const tree = context.exports.TextInput({ onSend: (content) => { sent = UserMsg({ name: 'user', content }); } }, null);
    function find(node) {
      if (!node || typeof node !== 'object') return;
      if (node.type === 'Button' && node.props.onClick && node.props.disabled === false && node.props.children?.type === 'ArrowUp') return node;
      for (const child of [node.props?.children].flat(Infinity)) {
        const found = find(child);
        if (found) return found;
      }
    }
    const button = find(tree);
    assert.ok(button, 'enabled send button');
    button.props.onClick();
    assert.equal(sent.content[0].text, 'local send test');
    assert.ok(sent.id);
    assert.ok(sent.content[0].id);
  } finally {
    Object.defineProperty(globalThis, 'crypto', descriptor);
  }
});
