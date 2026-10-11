import os
from pathlib import Path
import socket

import numpy as np
import pytest
from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, processors

from backend.ml.contextual import encode_rows, pad_batch, empty_predictions, collect_predictions
from backend.ml.contextual_predict import extract, load_assets
from backend.ml.predict import ExtractorUnavailableError


def small_tokenizer():
    tokenizer = Tokenizer(models.WordPiece(vocab={"[UNK]": 0, "[CLS]": 1, "[SEP]": 2, "python": 3}, unk_token="[UNK]"))
    tokenizer.normalizer = normalizers.BertNormalizer(lowercase=True)
    tokenizer.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    tokenizer.post_processor = processors.TemplateProcessing(single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 1), ("[SEP]", 2)])
    tokenizer.enable_truncation(max_length=8, stride=2)
    return tokenizer


def test_word_alignment_retains_control_characters_and_overflow_once():
    rows = [{"tokens": ["\u200bPython", "\x95", *(["Python"] * 21)],
             "tags_skill": ["B"] * 23, "tags_knowledge": ["O"] * 23}]
    chunks = encode_rows(small_tokenizer(), rows)
    words = [word for chunk in chunks for word in chunk["word_ids"] if word >= 0]
    assert words == list(range(23))
    assert len(chunks) > 1
    arrays = pad_batch(chunks)
    assert (arrays["labels"][:, :, 0] == 1).sum() == 23
    predictions = empty_predictions(rows)
    logits = np.zeros((*arrays["input_ids"].shape, 2, 3))
    logits[:, :, 0, 1] = 1
    collect_predictions(predictions, chunks, logits)
    assert predictions["skill"][0] == ["B"] * 23


def test_missing_contextual_assets_fail_explicitly(tmp_path):
    with pytest.raises(ExtractorUnavailableError):
        load_assets(tmp_path)


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual model")
def test_contextual_runtime_is_offline_repeatable_and_preserves_unicode(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *args: (_ for _ in ()).throw(AssertionError("Network forbidden")))
    load_assets.cache_clear()
    text = "🧭 Experience with Python and SQL. Excellent communication skills."
    first = extract(text, Path(".models/skillspan-distilbert"))
    assert first == extract(text, Path(".models/skillspan-distilbert"))
    assert first["spans"]
    assert all(text[span["start"]:span["end"]] == span["text"] for span in first["spans"])
    # Process the entire input, including a skill after more than one model window.
    long_text = " ".join(["word"] * 600) + ". Experience with Python and SQL."
    spans = extract(long_text, Path(".models/skillspan-distilbert"))["spans"]
    assert any(span["text"] == "Python" and span["start"] > 2000 for span in spans)
