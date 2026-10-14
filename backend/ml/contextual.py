"""Shared word alignment for contextual training and local ONNX inference."""

import numpy as np

from backend.ml.data import HEADS

LABELS = ["O", "B", "I"]
ENCODING_VERSION = "wordpieces-overlap-v1"
MAX_LENGTH = 256
STRIDE = 32


def encode_rows(tokenizer, rows: list[dict]) -> list[dict]:
    """Supervise each word once, retaining all words in long sentences."""
    chunks = []
    for row_index, row in enumerate(rows):
        # Some corpus bullets are control characters removed by BERT normalization.
        # Keep their label positions with an unknown token instead of dropping words.
        words = [word if tokenizer.normalizer.normalize_str(word).strip() else "[UNK]"
                 for word in row["tokens"]]
        encoded = tokenizer.encode(words, is_pretokenized=True)
        seen = set()
        for part in [encoded, *encoded.overflowing]:
            word_ids = []
            for word in part.word_ids:
                if word is None or word in seen:
                    word_ids.append(-1)
                else:
                    word_ids.append(word)
                    seen.add(word)
            if not any(word >= 0 for word in word_ids):
                continue
            chunk = {"row": row_index, "word_ids": word_ids,
                     "input_ids": part.ids, "attention_mask": part.attention_mask}
            if all(column in row for column in HEADS.values()):
                chunk["labels"] = [
                    [LABELS.index(row[column][word]) if word >= 0 else -100 for column in HEADS.values()]
                    for word in word_ids
                ]
            chunks.append(chunk)
        if len(seen) != len(row["tokens"]):
            raise ValueError("Tokenizer did not preserve every input word")
    return chunks


def pad_batch(chunks: list[dict]) -> dict[str, np.ndarray]:
    width = max(len(chunk["input_ids"]) for chunk in chunks)
    width = ((width + 7) // 8) * 8
    ids = np.zeros((len(chunks), width), dtype=np.int64)
    mask = np.zeros_like(ids)
    labels = np.full((len(chunks), width, len(HEADS)), -100, dtype=np.int64)
    for index, chunk in enumerate(chunks):
        size = len(chunk["input_ids"])
        ids[index, :size] = chunk["input_ids"]
        mask[index, :size] = chunk["attention_mask"]
        if "labels" in chunk:
            labels[index, :size] = chunk["labels"]
    return {"input_ids": ids, "attention_mask": mask, "labels": labels}


def empty_predictions(rows: list[dict]) -> dict[str, list[list[str]]]:
    return {head: [["O"] * len(row["tokens"]) for row in rows] for head in HEADS}


def collect_predictions(predictions: dict, chunks: list[dict], logits: np.ndarray) -> None:
    choices = logits.argmax(axis=-1)
    for batch_index, chunk in enumerate(chunks):
        for position, word in enumerate(chunk["word_ids"]):
            if word >= 0:
                for head_index, head in enumerate(HEADS):
                    predictions[head][chunk["row"]][word] = LABELS[int(choices[batch_index, position, head_index])]
