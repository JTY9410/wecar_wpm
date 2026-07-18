from app.services import rag_store
from scripts import qlora_finetune


def test_rag_skips_without_deps(app, db, monkeypatch):
    monkeypatch.setattr(rag_store, "_deps", lambda: (None, None))
    res = rag_store.embed_records([])
    assert res["status"] == "SKIP"


def test_qlora_skip_without_gpu(monkeypatch):
    monkeypatch.setattr(qlora_finetune, "gpu_available", lambda: False)
    res = qlora_finetune.run()
    assert res["status"] == "SKIP"
    assert res["reason"] == "no_gpu"
