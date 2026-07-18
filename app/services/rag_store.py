"""RAG 벡터 적재 (PRD §7.2). Lazy imports; SKIP gracefully when libs absent."""
from config import Config


def _deps():
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
        return SentenceTransformer, chromadb
    except ImportError:
        return None, None


def is_available():
    st, chroma = _deps()
    return st is not None and chroma is not None


def embed_records(records):
    """records: iterable of AuctionRecord. Returns dict(status, count)."""
    SentenceTransformer, chromadb = _deps()
    if SentenceTransformer is None:
        return {"status": "SKIP", "reason": "sentence-transformers/chromadb 미설치", "count": 0}

    docs, ids, metas = [], [], []
    for r in records:
        text = " ".join(str(x) for x in [r.car_name, r.fuel, r.km_bin,
                                         r.accident_detail, r.imported] if x)
        if not text.strip():
            continue
        docs.append(text)
        ids.append(str(r.id))
        metas.append({"car_code": r.car_code or "", "week_no": r.week_no or ""})
    if not docs:
        return {"status": "SUCCESS", "count": 0}

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(docs).tolist()
    client = chromadb.PersistentClient(path=Config.CHROMA_PATH)
    coll = client.get_or_create_collection("auction_records")
    coll.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
    return {"status": "SUCCESS", "count": len(docs)}
