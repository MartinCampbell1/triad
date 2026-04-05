from triad.proxy.translator import translate_to_provider_prompt


def test_translate_string_input():
    body = {"input": "Fix the auth bug"}
    assert translate_to_provider_prompt(body) == "Fix the auth bug"


def test_translate_messages_list():
    body = {"input": [
        {"role": "user", "content": "Fix the auth bug"},
    ]}
    result = translate_to_provider_prompt(body)
    assert "Fix the auth bug" in result


def test_translate_nested_content():
    body = {"input": [
        {"role": "user", "content": [
            {"type": "input_text", "text": "Review this code"}
        ]},
    ]}
    result = translate_to_provider_prompt(body)
    assert "Review this code" in result


def test_translate_chat_completions_fallback():
    body = {"messages": [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Help me"},
    ]}
    result = translate_to_provider_prompt(body)
    assert "Help me" in result


def test_translate_empty():
    assert translate_to_provider_prompt({}) == ""


def test_translate_prompt_field():
    body = {"prompt": "Simple prompt"}
    assert translate_to_provider_prompt(body) == "Simple prompt"
