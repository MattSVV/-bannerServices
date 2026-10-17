"""T15d: fixes for the LOW and INFO findings of the T15 verification (``odd/findings/t15d-findings.md``)."""
import struct
import zlib

import pytest
from contrib.plugins.portadas.application.design_prompt import (
    MAX_PROBLEMS,
    MAX_PROBLEMS_CHARS,
    build_repair_prompt,
)
from contrib.plugins.portadas.application.icon_upload import png_decode_bytes
from contrib.plugins.portadas.domain.cover import CoverError
from contrib.plugins.portadas.lib.ai_notice import FileNoticeStore
from contrib.plugins.portadas.lib.ai_settings import BASE_URL_KEY, PROVIDER_KEY
from contrib.plugins.portadas.lib.iconimage import MAX_DECODE_BYTES, prepare_png_icon
from openlp.core.common.settings import Settings

from .fakes import make_services
from .test_edit_form import Form
from .test_edit_form_ai import FakeDesigner

# --- finding 1: the first-use notice is bound to its destination ----------------------------------------------------


class AskingForm(Form):
    def confirm_data_use(self, destination):
        self.asked = getattr(self, 'asked', []) + [destination]
        return True


@pytest.fixture
def ai_form(qtbot, openlp_env, tmp_path):
    designer = FakeDesigner(gated=False)
    svc = make_services(tmp_path)
    svc.designer_factory = lambda: designer
    form = AskingForm(None, svc)
    qtbot.addWidget(form)
    form.load_cover(None)
    form.title_main_edit.setText('Resistir')
    form.key_verse_edit.setText('Santiago 4:7')
    form.designer = designer
    return form


def set_value(openlp_env, key, value):
    settings = Settings()  # a fresh object, written to the shared file when it goes out of scope
    settings.setValue(key, value)
    settings.sync()
    del settings


def design_once(form, qtbot):
    count = len(form.designer.requests)
    form.design_button.click()
    qtbot.waitUntil(lambda: form._design_job is None and len(form.designer.requests) == count + 1, timeout=5000)


def test_the_notice_is_asked_again_when_the_provider_changes(ai_form, qtbot, openlp_env):
    set_value(openlp_env, PROVIDER_KEY, 'openai')
    design_once(ai_form, qtbot)
    design_once(ai_form, qtbot)
    assert len(ai_form.asked) == 1

    set_value(openlp_env, PROVIDER_KEY, 'anthropic')
    design_once(ai_form, qtbot)

    assert len(ai_form.asked) == 2


def test_the_notice_is_asked_again_when_the_server_changes(ai_form, qtbot, openlp_env):
    set_value(openlp_env, PROVIDER_KEY, 'openai_compatible')
    set_value(openlp_env, BASE_URL_KEY, 'https://llm.example.org/v1')
    design_once(ai_form, qtbot)
    set_value(openlp_env, BASE_URL_KEY, 'https://llm.example.org/v2')  # same origin: not asked again
    design_once(ai_form, qtbot)
    assert len(ai_form.asked) == 1

    set_value(openlp_env, BASE_URL_KEY, 'https://evil.example/v1')
    design_once(ai_form, qtbot)

    assert len(ai_form.asked) == 2


def test_an_imported_settings_file_cannot_accept_the_notice(ai_form, qtbot, openlp_env):
    # What OpenLP's "import settings" can do: write any key into the settings store, including the old flag.
    set_value(openlp_env, 'portadas/ai data notice accepted', True)
    set_value(openlp_env, PROVIDER_KEY, 'openai')

    design_once(ai_form, qtbot)

    assert len(ai_form.asked) == 1


def test_the_accepted_destinations_survive_a_restart_and_a_broken_file_asks_again(tmp_path):
    path = tmp_path / 'ai-notice.json'
    FileNoticeStore(path).accept('openai')

    assert FileNoticeStore(path).accepted('openai') and not FileNoticeStore(path).accepted('gemini')

    path.write_text('{not json')
    assert not FileNoticeStore(path).accepted('openai')
    FileNoticeStore(path).accept('gemini')  # a damaged file is replaced
    assert FileNoticeStore(path).accepted('gemini')


def test_the_notice_store_is_bounded(tmp_path):
    store = FileNoticeStore(tmp_path / 'n.json')
    for number in range(100):
        store.accept(f'https://h{number}.example')

    assert store.accepted('https://h99.example') and not store.accepted('https://h0.example')


# --- finding 2: the repair prompt is bounded in count and total -----------------------------------------------------

def test_the_repair_prompt_lists_a_bounded_number_of_problems():
    problems = [f'problem number {number} ' + 'x' * 250 for number in range(9000)]

    prompt = build_repair_prompt('original request', 'previous', problems)

    listed = [line for line in prompt.splitlines() if line.startswith('- ')]
    assert len(listed) <= MAX_PROBLEMS + 1  # the ones listed, plus the "more" line
    assert sum(len(line) for line in listed) <= MAX_PROBLEMS_CHARS + 200
    assert len(prompt) < 40000
    assert 'problem number 0 ' in prompt and 'problem number 8999' not in prompt
    assert '8990 more' in prompt


def test_few_problems_are_all_listed():
    prompt = build_repair_prompt('o', 'p', ['a', 'b'])

    assert '- a\n- b\n' in prompt and 'more' not in prompt


# --- finding 3: cancelling by picking a template clears the busy status ---------------------------------------------

def test_picking_a_template_while_designing_clears_the_designing_status(qtbot, openlp_env, tmp_path):
    designer = FakeDesigner()
    svc = make_services(tmp_path)
    svc.designer_factory = lambda: designer
    form = Form(None, svc)
    qtbot.addWidget(form)
    form.load_cover(None)
    form.title_main_edit.setText('Resistir')
    form.key_verse_edit.setText('Santiago 4:7')
    form.design_button.click()
    assert designer.entered.wait(5) and 'Designing' in form.status_label.text()

    form.template_list.setCurrentRow(1)
    designer.gate.set()

    assert 'Designing' not in form.status_label.text()


# --- finding 4: the decode bound counts bit depth --------------------------------------------------------------------

def sparse_png(width, height, depth, color_type, channels):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))
    row = b'\x00' + bytes(width * channels * depth // 8)
    packer = zlib.compressobj(9)
    idat = b''.join(packer.compress(row) for _ in range(height)) + packer.flush()
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, color_type, 0, 0, 0)) +
            chunk(b'IDAT', idat) + chunk(b'IEND', b''))


def test_decode_cost_is_weighted_by_bit_depth():
    assert png_decode_bytes(sparse_png(100, 100, 8, 6, 4)) == 100 * 100 * 4
    assert png_decode_bytes(sparse_png(100, 100, 16, 6, 4)) == 100 * 100 * 8


def test_a_deep_png_that_would_exceed_the_memory_budget_is_refused_before_decoding(qapp, tmp_path):
    path = tmp_path / 'deep.png'
    path.write_bytes(sparse_png(4000, 4000, 16, 6, 4))  # 16M pixels: 128 MB once decoded
    assert 4000 * 4000 * 8 > MAX_DECODE_BYTES

    with pytest.raises(CoverError):
        prepare_png_icon(path)


def test_a_plain_png_of_the_same_size_is_still_accepted(qapp, tmp_path):
    path = tmp_path / 'plain.png'
    path.write_bytes(sparse_png(3000, 3000, 8, 6, 4))  # 36 MB once decoded

    assert prepare_png_icon(path).startswith(b'\x89PNG')
