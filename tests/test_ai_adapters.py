# -*- coding: utf-8 -*-

##########################################################################
# Portadas - sermon cover plugin for OpenLP                              #
# ---------------------------------------------------------------------- #
# Copyright (c) 2026 Portadas contributors                               #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
"""The four provider adapters, driven by a scripted session: request shape, parsing, errors, retries, redaction."""
import logging
import traceback

import pytest
import requests
from contrib.plugins.portadas.adapters.ai import create_designer
from contrib.plugins.portadas.adapters.ai import test_connection as connection_test
from contrib.plugins.portadas.adapters.ai.http import MAX_RESPONSE_BYTES
from contrib.plugins.portadas.application.ai_config import AiConfig
from contrib.plugins.portadas.application.ports import DesignError, DesignRequest, UnusableReply
from contrib.plugins.portadas.security.redaction import clear_secrets

from .ai_support import (
    DESIGN_JSON,
    GOOD_HTML,
    GOOD_SVG,
    KEY,
    FakeResponse,
    FakeSession,
    Sleeper,
    anthropic_body,
    gemini_body,
    openai_body,
    timeout_error,
)

REQUEST = DesignRequest('SYSTEM RULES', 'USER TEXT')
BODIES = {'openai': openai_body, 'anthropic': anthropic_body, 'gemini': gemini_body, 'openai_compatible': openai_body}
COMPAT_URL = 'https://llm.example.org/v1'


@pytest.fixture(autouse=True)
def _forget_keys():
    clear_secrets()
    yield
    clear_secrets()


def config(provider, model='', timeout=60, base_url=''):
    default_url = COMPAT_URL if provider == 'openai_compatible' else ''
    return AiConfig(provider, model, base_url or default_url, timeout)


def make(provider, *script, model='', timeout=60, key=KEY):
    session, sleeper = FakeSession(*script), Sleeper()
    designer = create_designer(config(provider, model, timeout), key, session=session, sleep=sleeper)
    return designer, session, sleeper


def ok(provider, text=DESIGN_JSON):
    return FakeResponse(200, BODIES[provider](text))


ALL = ['openai', 'anthropic', 'gemini', 'openai_compatible']


# --- request shape -------------------------------------------------------------------------------------------------

def test_openai_request_shape():
    designer, session, _ = make('openai', ok('openai'), model='gpt-x')

    designer.design(REQUEST)

    call = session.calls[0]
    assert (call['method'], call['url']) == ('POST', 'https://api.openai.com/v1/chat/completions')
    assert call['headers']['Authorization'] == f'Bearer {KEY}'
    body = call['json']
    assert body['model'] == 'gpt-x' and body['response_format'] == {'type': 'json_object'}
    assert body['messages'] == [{'role': 'system', 'content': 'SYSTEM RULES'}, {'role': 'user', 'content': 'USER TEXT'}]
    assert body['max_completion_tokens'] > 1000


def test_anthropic_request_shape():
    designer, session, _ = make('anthropic', ok('anthropic'), model='claude-x')

    designer.design(REQUEST)

    call = session.calls[0]
    assert (call['method'], call['url']) == ('POST', 'https://api.anthropic.com/v1/messages')
    assert call['headers']['x-api-key'] == KEY and call['headers']['anthropic-version'] == '2023-06-01'
    assert 'Authorization' not in call['headers']
    body = call['json']
    assert body['model'] == 'claude-x' and body['system'] == 'SYSTEM RULES' and body['max_tokens'] > 1000
    assert body['messages'] == [{'role': 'user', 'content': 'USER TEXT'}]


def test_gemini_request_shape_sends_the_key_in_a_header_never_in_the_url():
    designer, session, _ = make('gemini', ok('gemini'), model='gemini-x')

    designer.design(REQUEST)

    call = session.calls[0]
    assert call['url'] == 'https://generativelanguage.googleapis.com/v1beta/models/gemini-x:generateContent'
    assert call['headers']['x-goog-api-key'] == KEY
    assert KEY not in call['url'] and '?' not in call['url'] and 'key=' not in call['url']
    body = call['json']
    assert body['systemInstruction'] == {'parts': [{'text': 'SYSTEM RULES'}]}
    assert body['contents'] == [{'role': 'user', 'parts': [{'text': 'USER TEXT'}]}]
    assert body['generationConfig']['responseMimeType'] == 'application/json'


def test_gemini_accepts_a_models_prefix_and_refuses_path_tricks():
    designer, session, _ = make('gemini', ok('gemini'), model='models/gemini-x')
    designer.design(REQUEST)
    assert session.calls[0]['url'].endswith('/models/gemini-x:generateContent')

    for bad in ('../admin', 'a/b', 'x?y=1', 'a b'):
        designer, _, _ = make('gemini', ok('gemini'), model=bad)
        with pytest.raises(DesignError, match='model name'):
            designer.design(REQUEST)


def test_openai_compatible_uses_the_base_url_and_max_tokens():
    designer, session, _ = make('openai_compatible', ok('openai_compatible'), model='llama3.1:8b')

    designer.design(REQUEST)

    call = session.calls[0]
    assert call['url'] == COMPAT_URL + '/chat/completions'
    assert call['headers']['Authorization'] == f'Bearer {KEY}'
    assert call['json']['model'] == 'llama3.1:8b' and 'max_tokens' in call['json']
    assert 'max_completion_tokens' not in call['json']


def test_openai_compatible_works_without_a_key_for_local_servers():
    session = FakeSession(ok('openai_compatible'))
    cfg = config('openai_compatible', base_url='http://localhost:11434/v1/')
    designer = create_designer(cfg, None, session=session, sleep=Sleeper())

    designer.design(REQUEST)

    assert session.calls[0]['url'] == 'http://localhost:11434/v1/chat/completions'
    assert 'Authorization' not in session.calls[0]['headers']


def test_an_invalid_compatible_base_url_is_refused_before_any_request():
    session = FakeSession(ok('openai'))
    cfg = config('openai_compatible', base_url='http://evil.example.org/v1')

    with pytest.raises(DesignError, match='http'):
        create_designer(cfg, KEY, session=session, sleep=Sleeper()).design(REQUEST)

    assert session.calls == []


@pytest.mark.parametrize('provider', ['openai', 'anthropic', 'gemini'])
def test_a_hosted_provider_needs_a_key(provider):
    designer, session, _ = make(provider, ok(provider), key=None)

    with pytest.raises(DesignError, match='API key'):
        designer.design(REQUEST)

    assert session.calls == []


@pytest.mark.parametrize('bad_key', ['has space', 'new\nline', 'tab\t', ''])
def test_a_key_that_cannot_be_a_header_is_refused_without_echoing_it(bad_key):
    designer, session, _ = make('openai', ok('openai'), key=bad_key)

    with pytest.raises(DesignError) as caught:
        designer.design(REQUEST)

    assert bad_key.strip() == '' or bad_key not in str(caught.value)
    assert session.calls == []


@pytest.mark.parametrize('provider', ALL)
def test_every_request_is_bounded_and_never_follows_redirects(provider):
    designer, session, _ = make(provider, ok(provider), timeout=1000)

    designer.design(REQUEST)

    call = session.calls[0]
    assert call['allow_redirects'] is False and call['stream'] is True
    assert call['timeout'][1] == 300  # the configured timeout is clamped (bounded_timeout)
    assert call['timeout'][0] <= 15


# --- parsing ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('provider', ALL)
def test_the_design_is_parsed(provider):
    designer, _, _ = make(provider, ok(provider))

    proposal = designer.design(REQUEST)

    assert proposal.template_html == GOOD_HTML and proposal.icon_svg == GOOD_SVG and proposal.notes == 'warm'


@pytest.mark.parametrize('provider', ALL)
def test_json_inside_code_fences_is_accepted(provider):
    designer, _, _ = make(provider, ok(provider, '```json\n' + DESIGN_JSON + '\n```'))

    assert designer.design(REQUEST).template_html == GOOD_HTML


def test_openai_content_given_as_parts_is_joined():
    body = {'choices': [{'message': {'content': [{'type': 'text', 'text': DESIGN_JSON[:20]},
                                                  {'type': 'text', 'text': DESIGN_JSON[20:]}]}}]}
    designer, _, _ = make('openai', FakeResponse(200, body))

    assert designer.design(REQUEST).template_html == GOOD_HTML


@pytest.mark.parametrize('provider,body', [
    ('openai', {'choices': []}), ('openai', {'nope': 1}), ('anthropic', {'content': []}),
    ('anthropic', {'content': [{'type': 'tool_use'}]}), ('gemini', {'candidates': []}),
    ('gemini', {'candidates': [{'content': {'parts': []}}]})])
def test_a_reply_without_text_is_an_unusable_reply(provider, body):
    designer, _, _ = make(provider, FakeResponse(200, body))

    with pytest.raises(DesignError):
        designer.design(REQUEST)


def test_a_reply_that_is_not_a_design_is_an_unusable_reply_so_the_use_case_can_repair():
    designer, _, _ = make('openai', ok('openai', 'I cannot help with that.'))

    with pytest.raises(UnusableReply):
        designer.design(REQUEST)


def test_a_refusal_is_reported():
    body = {'choices': [{'message': {'content': None, 'refusal': 'I cannot do that'}}]}
    designer, _, _ = make('openai', FakeResponse(200, body))

    with pytest.raises(DesignError, match='refused'):
        designer.design(REQUEST)


def test_an_anthropic_refusal_is_reported():
    designer, _, _ = make('anthropic', FakeResponse(200, {'content': [], 'stop_reason': 'refusal'}))

    with pytest.raises(DesignError, match='refused'):
        designer.design(REQUEST)


def test_an_anthropic_answer_without_content_blocks_is_an_unexpected_answer():
    designer, _, _ = make('anthropic', FakeResponse(200, {'stop_reason': 'end_turn'}))

    with pytest.raises(DesignError, match='unexpected answer'):
        designer.design(REQUEST)


def test_gemini_blocked_prompts_are_reported():
    designer, _, _ = make('gemini', FakeResponse(200, {'promptFeedback': {'blockReason': 'SAFETY'}}))

    with pytest.raises(DesignError, match='blocked'):
        designer.design(REQUEST)


# --- errors, retries, size cap ---------------------------------------------------------------------------------------

@pytest.mark.parametrize('provider', ALL)
@pytest.mark.parametrize('status,fragment', [(401, 'API key'), (403, 'API key'), (404, 'not found'),
                                             (400, 'rejected the request'), (418, 'HTTP 418')])
def test_client_errors_are_mapped_and_not_retried(provider, status, fragment):
    designer, session, sleeper = make(provider, FakeResponse(status, {'error': {'message': 'nope'}}))

    with pytest.raises(DesignError, match=fragment):
        designer.design(REQUEST)

    assert len(session.calls) == 1 and sleeper.delays == []


@pytest.mark.parametrize('provider', ALL)
@pytest.mark.parametrize('status', [429, 500, 502, 503])
def test_retryable_errors_are_retried_at_most_twice_with_backoff(provider, status):
    designer, session, sleeper = make(provider, FakeResponse(status, {'error': {'message': 'busy'}}))

    with pytest.raises(DesignError):
        designer.design(REQUEST)

    assert len(session.calls) == 3
    assert sleeper.delays == [1.0, 2.0]


def test_a_retry_that_succeeds_returns_the_design():
    designer, session, sleeper = make('anthropic', FakeResponse(529, {}), FakeResponse(429, {}), ok('anthropic'))

    assert designer.design(REQUEST).template_html == GOOD_HTML
    assert len(session.calls) == 3 and len(sleeper.delays) == 2


def test_retry_after_is_honoured_but_capped():
    designer, _, sleeper = make('openai', FakeResponse(429, {}, {'Retry-After': '3'}),
                                FakeResponse(429, {}, {'Retry-After': '9999'}), ok('openai'))

    designer.design(REQUEST)

    assert sleeper.delays == [3.0, 10.0]


def test_a_timeout_is_a_clear_error_without_the_key_and_is_not_retried():
    designer, session, _ = make('openai', timeout_error())

    with pytest.raises(DesignError, match='did not answer in time') as caught:
        designer.design(REQUEST)

    assert KEY not in str(caught.value) and len(session.calls) == 1
    assert KEY not in ''.join(traceback.format_exception(caught.value))


def test_connection_errors_never_include_the_exception_text():
    error = requests.exceptions.ConnectionError(
        f'HTTPSConnectionPool(host=x): Max retries (Authorization: Bearer {KEY})')
    designer, _, _ = make('openai', error)

    with pytest.raises(DesignError, match='connect') as caught:
        designer.design(REQUEST)

    assert KEY not in str(caught.value)
    assert KEY not in ''.join(traceback.format_exception(caught.value))


def test_a_provider_message_that_echoes_the_key_is_redacted():
    body = {'error': {'message': f'Incorrect API key provided: {KEY}.'}}
    designer, _, _ = make('openai', FakeResponse(400, body))

    with pytest.raises(DesignError) as caught:
        designer.design(REQUEST)

    assert KEY not in str(caught.value) and 'Incorrect API key' in str(caught.value)


def test_a_provider_message_is_shortened_and_cleaned():
    body = {'error': {'message': 'bad\x00 ' + 'x' * 2000 + '\nline'}}
    designer, _, _ = make('anthropic', FakeResponse(400, body))

    with pytest.raises(DesignError) as caught:
        designer.design(REQUEST)

    assert len(str(caught.value)) < 400 and '\x00' not in str(caught.value) and '\n' not in str(caught.value)


def test_redirects_are_errors():
    designer, session, _ = make('openai', FakeResponse(302, {}, {'Location': 'https://evil.example.org/'}))

    with pytest.raises(DesignError, match='redirect'):
        designer.design(REQUEST)

    assert len(session.calls) == 1


def test_an_oversized_response_is_refused_while_reading():
    response = FakeResponse(200, raw=b'{"x": "' + b'a' * (MAX_RESPONSE_BYTES + 100) + b'"}')
    designer, _, _ = make('openai', response)

    with pytest.raises(DesignError, match='too large'):
        designer.design(REQUEST)

    assert response.closed and response.chunks_read * 8192 < MAX_RESPONSE_BYTES + 3 * 8192


@pytest.mark.parametrize('raw', [b'<html>gateway</html>', b'', b'[1,2]', b'\xff\xfe'])
def test_a_body_that_is_not_a_json_object_is_an_error(raw):
    designer, _, _ = make('openai', FakeResponse(200, raw=raw))

    with pytest.raises(DesignError, match='unexpected'):
        designer.design(REQUEST)


def test_responses_are_always_closed():
    response = ok('openai')
    designer, _, _ = make('openai', response)

    designer.design(REQUEST)

    assert response.closed


@pytest.mark.parametrize('provider', ALL)
def test_the_key_never_reaches_the_logs(provider, caplog):
    caplog.set_level(logging.DEBUG)
    designer, _, _ = make(provider, FakeResponse(503, {'error': {'message': KEY}}), ok(provider))

    designer.design(REQUEST)

    assert KEY not in caplog.text and all(KEY not in str(record.args) for record in caplog.records)


# --- test_connection -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('provider,url,header', [
    ('openai', 'https://api.openai.com/v1/models/gpt-x', 'Authorization'),
    ('anthropic', 'https://api.anthropic.com/v1/models/gpt-x', 'x-api-key'),
    ('gemini', 'https://generativelanguage.googleapis.com/v1beta/models/gpt-x', 'x-goog-api-key')])
def test_the_connection_test_asks_for_the_model(provider, url, header):
    session = FakeSession(FakeResponse(200, {'id': 'gpt-x', 'name': 'models/gpt-x'}))

    message = connection_test(config(provider, 'gpt-x'), KEY, session=session, sleep=Sleeper())

    call = session.calls[0]
    assert (call['method'], call['url']) == ('GET', url)
    assert header in call['headers'] and KEY not in call['url'] and call['json'] is None
    assert 'gpt-x' in message and KEY not in message


def test_the_compatible_connection_test_lists_the_models():
    session = FakeSession(FakeResponse(200, {'data': [{'id': 'a'}, {'id': 'b'}]}))

    message = connection_test(config('openai_compatible', 'a'), None, session=session, sleep=Sleeper())

    assert session.calls[0]['url'] == COMPAT_URL + '/models'
    assert '2' in message


def test_the_connection_test_reports_a_bad_key_and_an_unknown_model():
    with pytest.raises(DesignError, match='API key'):
        connection_test(config('openai'), KEY, session=FakeSession(FakeResponse(401, {})), sleep=Sleeper())
    with pytest.raises(DesignError, match='not found'):
        connection_test(config('gemini', 'nope'), KEY, session=FakeSession(FakeResponse(404, {})), sleep=Sleeper())


def test_the_connection_test_without_a_key_explains_what_to_do():
    with pytest.raises(DesignError, match='API key'):
        connection_test(config('anthropic'), None, session=FakeSession(), sleep=Sleeper())


def test_the_default_model_is_used_when_the_field_is_empty():
    from contrib.plugins.portadas.application.ai_config import DEFAULT_MODELS
    designer, session, _ = make('anthropic', ok('anthropic'))

    designer.design(REQUEST)

    assert session.calls[0]['json']['model'] == DEFAULT_MODELS['anthropic']


def test_an_unknown_provider_is_refused():
    with pytest.raises(DesignError):
        create_designer(AiConfig('evilcorp', '', '', 60), KEY)


# --- T12b: total deadline, cancellation, no proxy/netrc from the environment ------------------------------------------

class FakeClock:
    """A monotonic clock the test advances by hand."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TricklingResponse(FakeResponse):
    """A body that arrives one small chunk per second of (fake) time and never ends."""

    def __init__(self, clock, chunks=10000):
        super().__init__(200, {})
        self.clock, self.limit = clock, chunks

    def iter_content(self, chunk_size=8192):
        for _ in range(self.limit):
            self.chunks_read += 1
            self.clock.now += 1.0
            yield b' '


def with_clock(provider, clock, *script, timeout=5):
    session, sleeper = FakeSession(*script), Sleeper()
    designer = create_designer(config(provider, '', timeout), KEY, session=session, sleep=sleeper, clock=clock)
    return designer, session, sleeper


def test_a_body_that_trickles_in_is_cut_off_by_a_total_deadline():
    clock = FakeClock()
    response = TricklingResponse(clock)
    designer, _, _ = with_clock('openai', clock, response)

    with pytest.raises(DesignError, match='in time'):
        designer.design(REQUEST)

    assert response.chunks_read <= 11 and response.closed  # 5 s timeout x 2: never read to the end


def test_the_deadline_covers_the_whole_retry_loop_including_the_backoff():
    clock = FakeClock()
    designer, session, sleeper = with_clock('openai', clock, FakeResponse(503, {}, {'Retry-After': '8'}))
    sleeper_calls = sleeper.delays

    def advancing_sleep(seconds):
        sleeper_calls.append(seconds)
        clock.now += seconds

    designer.sleep = advancing_sleep

    with pytest.raises(DesignError, match='in time'):
        designer.design(REQUEST)

    assert len(session.calls) <= 2  # 8 s of backoff already used the 10 s budget of a 5 s timeout


def test_each_request_is_given_only_the_time_that_is_left():
    clock = FakeClock()
    designer, session, _ = with_clock('openai', clock, ok('openai'))
    clock.now = 3.0

    designer.design(REQUEST)

    connect, read = session.calls[0]['timeout']
    assert connect <= 5 and read <= 5


def test_a_cancelled_call_stops_reading_and_closes_the_response():
    from contrib.plugins.portadas.application import cancellation
    clock = FakeClock()
    response = TricklingResponse(clock)
    designer, _, _ = with_clock('openai', clock, response, timeout=60)
    event = cancellation.CancelEvent()
    seen = []

    original = response.iter_content

    def cancelling(chunk_size=8192):
        for chunk in original(chunk_size):
            seen.append(1)
            if len(seen) == 3:
                event.set()
            yield chunk

    response.iter_content = cancelling

    with cancellation.bound(event):
        with pytest.raises(DesignError, match='cancel'):
            designer.design(REQUEST)

    assert response.chunks_read <= 4 and response.closed


def test_a_call_that_was_cancelled_before_it_started_sends_nothing():
    from contrib.plugins.portadas.application import cancellation
    designer, session, _ = make('openai', ok('openai'))
    event = cancellation.CancelEvent()
    event.set()

    with cancellation.bound(event):
        with pytest.raises(DesignError, match='cancel'):
            designer.design(REQUEST)

    assert session.calls == []


def test_the_default_session_ignores_proxy_variables_and_netrc(monkeypatch):
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.invalid:3128')
    monkeypatch.setenv('HTTP_PROXY', 'http://proxy.invalid:3128')
    designer = create_designer(config('openai'), KEY)

    assert designer.session.trust_env is False
    settings = designer.session.merge_environment_settings('https://api.openai.com/v1', {}, None, None, None)
    assert settings['proxies'] == {}
