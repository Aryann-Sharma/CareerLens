import json

import pytest

from backend.ml import train
from backend.ml.data import HEADS, REVISION, clean_splits, digest, load_split
from backend.ml.features import bio_spans, sentence_features
from backend.ml.metrics import evaluate, lexicon_predict
from backend.ml.predict import ExtractorUnavailableError, extract, load_assets, token_sentences


def row(tokens, tags, source="tech"):
    return {"idx": 1, "source": source, "tokens": tokens,
            "tags_skill": tags, "tags_knowledge": tags}


def test_deduplication_preserves_official_boundaries():
    splits, audit = clean_splits({
        "train": [row(["Python"], ["B"]), row(["PYTHON"], ["B"])],
        "dev": [row(["Python"], ["B"]), row(["SQL"], ["B"])],
        "test": [row(["sql"], ["B"]), row(["Java"], ["B"])],
    })
    assert [r["tokens"] for r in splits["train"]] == [["Python"]]
    assert [r["tokens"] for r in splits["dev"]] == [["SQL"]]
    assert [r["tokens"] for r in splits["test"]] == [["Java"]]
    assert all(item["duplicates_removed"] == 1 for item in audit.values())


def test_invalid_labels_are_rejected(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps(row(["Python", "SQL"], ["B"])))
    with pytest.raises(ValueError, match="misaligned"):
        load_split(path)


def test_features_do_not_use_labels_and_context_ablation_is_real():
    tokens = ["Use", "Python", "daily"]
    full = sentence_features(tokens, 2)
    alone = sentence_features(tokens, 0)
    assert full[1]["-1:word"] == "use"
    assert full[1]["1:word"] == "daily"
    assert "-1:word" not in alone[1]
    assert full[0]["bos"] and full[-1]["eos"]


def test_span_metrics_require_correct_boundaries():
    rows = [row(["write", "good", "code"], ["B", "I", "I"])]
    result = evaluate(rows, [["B", "I", "O"]], "tags_skill")["overall"]
    assert (result["tp"], result["fp"], result["fn"], result["f1"]) == (0, 1, 1, 0)
    assert bio_spans(["I", "I", "O", "B", "B"]) == {(0, 2), (3, 4), (4, 5)}
    with pytest.raises(ValueError):
        evaluate(rows, [], "tags_skill")


def test_long_dictionary_entries_do_not_extend_past_sentence_end():
    lexicon = {("python",), ("programming", "in", "python")}
    assert lexicon_predict(["Python"], lexicon) == ["B"]
    assert lexicon_predict(["Programming", "in", "Python"], lexicon) == ["B", "I", "I"]


def test_tokenizer_preserves_all_offsets_and_bounds_long_sequences():
    text = "Python, C++ and Node.js.\n" + "SQL " * 300
    sentences = token_sentences(text)
    assert max(map(len, sentences)) <= 256
    assert [token.group() for token in sentences[0]] == ["Python", ",", "C++", "and", "Node.js", "."]
    assert sum(len(s) for s in sentences) == 306
    for sentence in sentences:
        for token in sentence:
            assert text[token.start():token.end()] == token.group()


def test_missing_models_fail_without_a_download(tmp_path):
    with pytest.raises(ExtractorUnavailableError):
        extract("Python skills", tmp_path)


def test_full_training_pipeline_and_artifact_integrity(tmp_path, monkeypatch):
    data, output = tmp_path / "data", tmp_path / "model"
    data.mkdir()
    hashes = {}
    for name, prefix in (("train", "Use"), ("dev", "Learn"), ("test", "Need")):
        rows = [row([prefix, "Python", str(i)], ["O", "B", "O"]) for i in range(20)]
        path = data / f"{name}.json"
        path.write_text("\n".join(json.dumps(r) for r in rows))
        hashes[path.name] = digest(path)
    (data / "LICENSE").write_text("Test fixture")
    hashes["LICENSE"] = digest(data / "LICENSE")
    (data / "manifest.json").write_text(json.dumps({"revision": REVISION, "sha256": hashes}))
    monkeypatch.setattr(train, "CANDIDATES", [{"window": 0, "c1": 0.1, "c2": 0.1}])
    report = train.run(data, output, tmp_path / "report.json")
    assert report["test"]["combined"]["crf"]["f1"] == 1.0
    assert report["split_audit"]["train"]["retained"] == 20
    predictions = extract("Use Python 7", output)
    assert {span["label"] for span in predictions["spans"]} == set(HEADS)
    assert all(span["text"] == "Python" for span in predictions["spans"])
    with pytest.raises(ValueError, match="already exists"):
        train.run(data, output, tmp_path / "report.json")
    load_assets.cache_clear()
    (output / "skill.crfsuite").write_bytes(b"corrupt")
    with pytest.raises(ExtractorUnavailableError):
        extract("Python", output)
