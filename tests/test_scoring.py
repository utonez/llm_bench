from app.bench.scoring import score_response


def test_classification_exact_label_is_correct(classification_task):
    assert score_response(classification_task, "信用卡") is True


def test_classification_ignores_whitespace_and_trailing_punctuation(classification_task):
    assert score_response(classification_task, "  信用卡。\n") is True


def test_classification_uses_first_line_only(classification_task):
    assert score_response(classification_task, "信用卡\n因為提到刷卡") is True


def test_classification_wrong_label_is_incorrect(classification_task):
    assert score_response(classification_task, "貸款") is False


def test_extraction_matching_json_is_correct(extraction_task):
    text = '```json\n{"amount": "15000", "currency": "TWD"}\n```'

    assert score_response(extraction_task, text) is True


def test_extraction_accepts_numbers_and_extra_fields(extraction_task):
    text = '結果：{"amount": 15000, "currency": "twd", "note": "x"}'

    assert score_response(extraction_task, text) is True


def test_extraction_missing_field_is_incorrect(extraction_task):
    assert score_response(extraction_task, '{"amount": "15000"}') is False


def test_extraction_unparseable_json_is_incorrect(extraction_task):
    assert score_response(extraction_task, "amount is 15000") is False


def test_ungraded_category_returns_none(summary_task):
    assert score_response(summary_task, "任何摘要") is None
