import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

test('new-channel gallery hides DingTalk/Feishu; existing records stay manageable', async () => {
	const records = ['dingtalk', 'telegram', 'feishu', 'discord', 'custom'].map(
		(channel_type) => ({ channel_type, id: channel_type, enabled: true }),
	);
	const calls = [];
	const context = {
		exports: {},
		require: () => ({
			client: {
				get: async (path) => {
					calls.push(path);
					return records;
				},
			},
		}),
	};
	vm.runInNewContext(
		ts.transpileModule(readFileSync(new URL('../src/api/channel.ts', import.meta.url), 'utf8'), {
			compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
		}).outputText,
		context,
	);
	assert.deepEqual([...(await context.exports.channelApi.listTypes()).map((c) => c.channel_type)], [
		'telegram', 'discord', 'custom',
	]);
	assert.deepEqual([...(await context.exports.channelApi.list()).map((c) => c.channel_type)], [
		'dingtalk', 'telegram', 'feishu', 'discord', 'custom',
	]);
	assert.deepEqual(calls, ['/channels/types', '/channels/']);
	assert.equal(records.length, 5);
	assert.ok(records.every((channel) => channel.enabled));
});

test('Telegram forms require a matching public Bot ID and secret token', () => {
	const context = { exports: {}, require: () => ({}) };
	vm.runInNewContext(
		ts.transpileModule(
			readFileSync(new URL('../src/pages/channel/channel-form.tsx', import.meta.url), 'utf8'),
			{ compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } },
		).outputText,
		context,
	);
	const { defaultChannelForm, isChannelFormValid } = context.exports;
	const form = {
		...defaultChannelForm('agent'),
		name: 'Telegram bot',
		chatModelConfig: { type: 'openai', model: 'test', credential_id: 'credential' },
	};
	assert.equal(form.channelType, 'telegram');
	assert.equal(isChannelFormValid(form, 'create'), false);
	for (const credentials of [
		{ bot_id: '123' },
		{ bot_token: '123:secret' },
		{ bot_id: '999', bot_token: '123:secret' },
		{ bot_id: '123', bot_token: 'bad/token' },
	]) {
		assert.equal(isChannelFormValid({ ...form, credentials }, 'create'), false);
	}
	form.credentials = { bot_id: '123', bot_token: '123:secret' };
	assert.equal(isChannelFormValid(form, 'create'), true);
	assert.equal(isChannelFormValid({ ...form, credentials: {} }, 'edit'), true);
	assert.equal(isChannelFormValid({ ...form, channelType: 'discord', credentials: {} }, 'create'), true);
});
