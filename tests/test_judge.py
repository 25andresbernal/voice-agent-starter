from evals.judge import FakeJudge, OpenAIJudge, get_judge


def test_get_judge_returns_none_when_not_requested():
    assert get_judge(use_llm_judge=False, api_key="sk-anything") is None
    assert get_judge(use_llm_judge=False, api_key="") is None


def test_get_judge_falls_back_to_fake_judge_without_api_key():
    judge = get_judge(use_llm_judge=True, api_key="")
    assert isinstance(judge, FakeJudge)


def test_get_judge_returns_openai_judge_with_api_key():
    judge = get_judge(use_llm_judge=True, api_key="sk-test")
    assert isinstance(judge, OpenAIJudge)


def test_fake_judge_is_deterministic_and_bounded():
    turns = [
        {"speaker": "assistant", "text": "hi"},
        {"speaker": "user", "text": "hello"},
        {"speaker": "tool", "text": "", "tool_call": {"name": "x", "arguments": {}, "result": {}}},
    ]
    a = FakeJudge().score(turns)
    b = FakeJudge().score(turns)
    assert a.score == b.score
    assert 0.0 <= a.score <= 10.0
    assert a.rationale
