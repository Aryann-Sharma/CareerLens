"""Download the pinned model once; application requests never download files."""

import json

from huggingface_hub import hf_hub_download

from backend.app.core.config import get_settings
from backend.app.services.model_assets import MODEL_FILES, MODEL_REPOSITORY, MODEL_REVISION


def main() -> None:
    destination = get_settings().semantic_model_path
    destination.mkdir(parents=True, exist_ok=True)
    for filename in MODEL_FILES:
        hf_hub_download(
            repo_id=MODEL_REPOSITORY,
            revision=MODEL_REVISION,
            filename=filename,
            local_dir=destination,
        )
    (destination / "revision.json").write_text(
        json.dumps({"repository": MODEL_REPOSITORY, "revision": MODEL_REVISION}),
        encoding="utf-8",
    )
    print(f"Local model ready at {destination.resolve()}")


if __name__ == "__main__":
    main()
