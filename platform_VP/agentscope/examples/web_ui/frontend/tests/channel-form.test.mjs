import assert from 'node:assert/strict';
import test from 'node:test';

import { defaultChannelForm, isChannelFormValid, toCreateRequest } from '../src/pages/channel/channel-form-utils.ts';

const form = () => ({ ...defaultChannelForm('agent-fixture'), channelType: 'discord', name: 'My bot',
  chatModelConfig: { type: 'openai_credential', credential_id: 'fixture', model: 'offline', parameters: {} } });

test('a customer Discord create requires the owner ID in the allowlist', () => {
  for (const platformConfig of [{ owner_user_id: 'abc', allowed_user_ids: ['abc'] },
    { owner_user_id: '100', allowed_user_ids: [] }, { owner_user_id: '100', allowed_user_ids: ['200'] }]) {
    assert.equal(isChannelFormValid({ ...form(), platformConfig }, 'create', true), false);
  }
  const value = { ...form(), platformConfig: { owner_user_id: '100', allowed_user_ids: ['100'] } };
  assert.equal(isChannelFormValid(value, 'create', true), true);
  assert.deepEqual(toCreateRequest(value).platform_config.allowed_user_ids, ['100']);
});

test('a personal bot names its owner; access defaults to that owner', () => {
  assert.equal(isChannelFormValid(form(), 'create', true), false);
  assert.equal(isChannelFormValid({ ...form(), platformConfig: { owner_user_id: '100' } }, 'create', true), true);
  assert.equal(isChannelFormValid({ ...form(), platformConfig: { owner_user_id: '100', allowed_user_ids: [] } }, 'create', true), false);
});

test('BQL without a list remains compatible and an edited bot can explicitly block everyone', () => {
  assert.equal(isChannelFormValid(form(), 'create', false), true);
  assert.equal(isChannelFormValid({ ...form(), platformConfig: { allowed_user_ids: [] } }, 'edit', true), true);
  assert.equal(isChannelFormValid({ ...form(), channelType: 'feishu' }, 'create', true), true);
});
