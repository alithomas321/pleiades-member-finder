import json
from pathlib import Path

import pytest

import gaia_pleiades.pipeline as pipeline
from gaia_pleiades.config import ProjectPaths


def test_manifest_path_accepts_a_contained_regular_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    artifact = root / "outputs" / "metrics.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")

    assert pipeline._resolve_manifest_artifact(root, "outputs/metrics.json") == (artifact.resolve())


def test_verifier_preserves_missing_and_hash_mismatch_reporting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    paths = ProjectPaths(root)
    paths.outputs.mkdir(parents=True)
    (paths.outputs / "present.txt").write_text("present\n", encoding="utf-8")
    paths.artifact_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "files": {
                    "outputs/missing.txt": "unused",
                    "outputs/present.txt": "incorrect-digest",
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "verify_manifest", lambda _: {})

    with pytest.raises(RuntimeError) as error:
        pipeline.verify_artifacts(root)

    assert "outputs/missing.txt: missing" in str(error.value)
    assert "outputs/present.txt: expected incorrect-digest, got " in str(error.value)


def test_verifier_rejects_unsafe_manifest_paths_without_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    paths = ProjectPaths(root)
    paths.outputs.mkdir(parents=True)
    (paths.outputs / "directory").mkdir()

    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (paths.outputs / "external-link").symlink_to(outside)

    paths.artifact_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "files": {
                    "/dev/null": "unused",
                    "../outside.txt": "unused",
                    "outputs/nested/../../../outside.txt": "unused",
                    "outputs/external-link": "unused",
                    "outputs/directory": "unused",
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "verify_manifest", lambda _: {})

    def unexpected_hash(path: Path) -> str:
        raise AssertionError(f"unsafe path reached sha256_file: {path}")

    monkeypatch.setattr(pipeline, "sha256_file", unexpected_hash)

    with pytest.raises(RuntimeError, match="Unsafe artifact manifest path"):
        pipeline.verify_artifacts(root)
