"""Chat-completions transport for a model attested by the business API.

Converts one model response to the existing AG-UI transport. Tool continuation, grants,
budgets and durable intent remain owned by the existing Coordination adapter.
"""
import json
from uuid import uuid4

from adapters.backend.errors import AdapterError
from .models import output_limit


def chat_messages(wire, instructions, reply_format):
    messages = [{'role': 'system', 'content': instructions + '\n\n' + reply_format}]
    for message in wire['messages']:
        content = message.get('content') or ''
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get('type') == 'text':
                    parts.append({'type': 'text', 'text': part['text']})
                elif part.get('type') == 'image':
                    source = part['source']
                    parts.append({'type': 'image_url', 'image_url': {'url':
                        f"data:{source['mimeType']};base64,{source['value']}"}})
            content = parts
        entry = {'role': message['role'], 'content': content}
        if message.get('toolCalls'):
            entry['tool_calls'] = message['toolCalls']
        if message.get('toolCallId'):
            entry['tool_call_id'] = message['toolCallId']
        messages.append(entry)
    return messages


class RegisteredResponse:
    status_code = 200
    headers = {'content-type': 'text/event-stream'}

    def __init__(self, wire, message):
        self.wire, self.message = wire, message

    async def aiter_bytes(self):
        wire, message = self.wire, self.message
        events = [{'type': 'RUN_STARTED', 'threadId': wire['threadId'], 'runId': wire['runId']}]
        calls = message.get('tool_calls') or []
        said = message.get('content') or ''
        if not calls:
            if not isinstance(said, str) or not said.strip():
                raise AdapterError('model_returned_no_answer')
            said = json.dumps({'content': said.strip()}, ensure_ascii=False)
        if said:
            message_id = str(uuid4())
            events.extend([{'type': 'TEXT_MESSAGE_START', 'messageId': message_id, 'role': 'assistant'},
                {'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': said},
                {'type': 'TEXT_MESSAGE_END', 'messageId': message_id}])
        for call in calls:
            identity, function = call['id'], call['function']
            events.extend([{'type': 'TOOL_CALL_START', 'toolCallId': identity, 'toolCallName': function['name']},
                {'type': 'TOOL_CALL_ARGS', 'toolCallId': identity, 'delta': function['arguments']},
                {'type': 'TOOL_CALL_END', 'toolCallId': identity}])
        events.append({'type': 'RUN_FINISHED', 'threadId': wire['threadId'], 'runId': wire['runId']})
        yield ''.join('data: ' + json.dumps(event, ensure_ascii=False) + '\n\n' for event in events).encode()


async def registered_response(client, config, wire, instructions, reply_format):
    tools = [{'type': 'function', 'function': {'name': t['name'], 'description': t.get('description', ''),
        'parameters': t['parameters']}} for t in wire['tools']]
    body = {'model': config['model_name'], 'messages': chat_messages(wire, instructions, reply_format),
        **output_limit(config['provider'], 4096), **({'tools': tools} if tools else {}),
        **({'reasoning_effort': 'none'} if config['provider'] == 'openai' and config['model_name'] == 'gpt-6-luna' else {})}
    try:
        response = await client.post(config['base_url'].rstrip('/') + '/chat/completions',
            headers={'Authorization': 'Bearer ' + config['api_key']}, json=body, timeout=120)
        response.raise_for_status()
        data = response.json()
        message = data['choices'][0]['message']
        if not isinstance(message, dict):
            raise ValueError()
        effective = data.get('model')
        if effective and not str(effective).startswith(config['model_name']):
            raise AdapterError('effective_model_mismatch')
        return RegisteredResponse(wire, message)
    except (KeyError, IndexError, ValueError, TypeError):
        raise AdapterError('invalid_model_response') from None
