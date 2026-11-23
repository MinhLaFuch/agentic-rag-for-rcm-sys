import pytest

from package.embeddings.build_runtime_retrieval import build_runtime_retrieval


def test_disabled_dense_never_loads_missing_artifacts(tmp_path):
    options, provenance = build_runtime_retrieval(
        {"retrieval_mode": "bm25"}, {"enabled": False, "artifacts_dir": "missing"},
        corpus_path=tmp_path / "corpus.sqlite", default_embeddings=tmp_path / "missing.npz",
    )
    assert provenance["active"] == "bm25"
    assert options["query_encoder"] is None


def test_semantic_loader_survives_initialization_and_records_backend(tmp_path, monkeypatch):
    # Import the module explicitly: package consumers may re-export functions.
    import importlib
    module = importlib.import_module("package.embeddings.build_dense_retrieval")
    store, encoder = ["item"], object()
    monkeypatch.setattr(module, "build_dense_retrieval", lambda *a, **k: (store, encoder, {}))
    options, provenance = build_runtime_retrieval(
        {"fallback_to_bm25": False},
        {"enabled": True, "artifacts_dir": "artifact", "encoder_lock": "lock"},
        corpus_path=tmp_path / "corpus.sqlite", default_embeddings=tmp_path / "missing.npz",
    )
    assert options["vector_store"] is store
    assert options["query_encoder"] is encoder
    assert provenance["active"] == "hybrid"


@pytest.mark.parametrize("fallback", [False, True])
def test_missing_dense_is_strict_or_reported_fallback(tmp_path, fallback):
    args = ({"retrieval_mode": "hybrid", "fallback_to_bm25": fallback}, {"enabled": False})
    kwargs = dict(corpus_path=tmp_path / "corpus.sqlite", default_embeddings=tmp_path / "missing.npz")
    if not fallback:
        with pytest.raises(RuntimeError, match="fallback disabled"):
            build_runtime_retrieval(*args, **kwargs)
    else:
        options, provenance = build_runtime_retrieval(*args, **kwargs)
        assert provenance["active"] == "bm25_fallback"
        assert provenance["reason"]
        assert options["dense_search"] is None
