import os
import pytest

from backend.app.services.context_suggestions import evidence_units
from backend.app.services.duty_scope import denied_duty, workplace_commentary


@pytest.mark.parametrize('text',[
    'Write application code without supervision.',
    'Not only write application code, but test software carefully.',
    'Investigate production failures without being asked.',
    'Do not just watch dashboards; restore failed services.',
])
def test_affirmative_qualifiers_are_not_denials(text):
    # 'Do not just' still contains 'not just', which modifies 'watch'. The
    # extractor may abstain, but the whole passage is not a denied requirement.
    assert not denied_duty(text)


@pytest.mark.parametrize('text',[
    'We do not require programming without supervision.',
    'Not only training but no programming duties are involved.',
    'We never ask staff to write application code.',
    'No debugging, testing or deployment is required.',
    'Benefits include optional programming workshops.',
    'An employee review says the company used to teach programming.',
    'A former employee mocks the endless customer service meetings.',
])
def test_denials_and_explicit_background_do_not_become_duties(text):
    assert denied_duty(text) or workplace_commentary(text)
    assert evidence_units(text) == []


@pytest.mark.parametrize('text',[
    'Respond to employee reviews with a clear and professional explanation.',
    'Explain product benefits to prospective buyers.',
    'Debug our software gremlins and trace the failing request.',
    'Develop the employee benefits website and test each release.',
])
def test_legitimate_work_is_not_filtered_by_topic_words(text):
    assert not workplace_commentary(text)
    assert evidence_units(text)


def test_scope_resets_at_the_next_sentence_and_preserves_original_offsets():
    text = 'A former employee jokes about broken software, difficult customers and endless meetings. Write clear application code without supervision.'
    units = evidence_units(text)
    assert len(units) == 1 and units[0]['text'].startswith('Write clear')
    assert text[units[0]['start']:units[0]['end']] == units[0]['text']


def test_short_coordinated_duties_survive_without_duplicate_evidence():
    text = 'Write code, test changes, deploy releases.'
    assert evidence_units(text) == [{'text':text,'start':0,'end':len(text)}]
    text = 'Write code for our applications, test changes.'
    assert len(evidence_units(text)) == 1
    assert evidence_units('No coding, testing changes, deploying releases.') == []
    assert evidence_units('Benefits:\nFree coding lessons, testing classes, deployment workshops.') == []


@pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS') != '1',reason='Requires local sentence model')
def test_real_model_recovers_duties_and_ignores_explicit_background():
    from backend.app.services.context_suggestions import suggest_from_context
    for text in ('Write clear application code without supervision.', 'Write code, implement features, refactor applications.'):
        items,_ = suggest_from_context(text,[])
        assert 'Programming' in [s['skill'] for s in items]
        assert all(text[s['start']:s['end']] == s['evidence'] for s in items)
    assert suggest_from_context('An employee review says the company used to teach programming.',[])[0] == []
