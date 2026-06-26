"""
Hafta 1 — Vector DB Layer
ingest.py'den gelen chunk'lari embed eder, Qdrant'a yazar,
"bu fonksiyona en benzer N fonksiyon" sorgusunu calistirir.

EMBEDDING: Gercek sistemde nomic-embed-code kullanilir (asagida real_embed).
Sandbox model indiremedigi icin offline calisan toy_embed ile demo yapiyoruz.
Kendi makinende EMBED = real_embed yapip qdrant'i ayni birakman yeterli.
"""
import re, hashlib
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from ingest import ingest, Chunk

DIM = 256  # toy embedding boyutu (nomic-embed-code'da bu 768'dir)


# --- Embedding backend'leri -------------------------------------------------

def toy_embed(code: str) -> list[float]:
    """
    Offline demo embedding: token'lari hash'leyip frekans vektoru kurar (bag-of-tokens).
    Benzer token kumesine sahip kodlar cosine'da yakin cikar.
    NOT: Bu semantik DEGIL yuzeysel bir benzerliktir; gercek modelin yerini tutmaz,
    sadece pipeline'in calistigini gostermek icindir.
    """
    vec = [0.0] * DIM
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", code):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16) % DIM
        vec[h] += 1.0
    return vec


def real_embed(code: str) -> list[float]:
    """
    Gercek embedding. Kendi makinende su sekilde kullan (HuggingFace indirir):

        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("nomic-ai/nomic-embed-code")
        return _model.encode(code, normalize_embeddings=True).tolist()

    DIM'i de modelin cikti boyutuna (orn. 768) gore guncelle.
    """
    raise NotImplementedError("Kendi makinende sentence-transformers ile doldur.")


EMBED = toy_embed  # sandbox'ta toy; gercekte real_embed


# --- Qdrant pipeline --------------------------------------------------------

def build_store(chunks: list[Chunk], collection: str = "code") -> QdrantClient:
    client = QdrantClient(":memory:")  # gercekte QdrantClient(url="http://localhost:6333")
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
    )
    points = []
    for i, c in enumerate(chunks):
        points.append(PointStruct(
            id=i,
            vector=EMBED(c.code),
            payload={  # metadata: sorgudan sonra hangi fonksiyon oldugunu bilmek icin
                "file": c.file, "func": c.func, "lang": c.lang,
                "line_start": c.line_start, "line_end": c.line_end,
                "complexity": c.complexity, "is_method": c.is_method,
            },
        ))
    client.upsert(collection_name=collection, points=points)
    return client


def most_similar(client: QdrantClient, query_code: str, k: int = 5,
                 collection: str = "code"):
    hits = client.query_points(
        collection_name=collection,
        query=EMBED(query_code),
        limit=k + 1,  # kendisi de donebilir, +1 alip kendini eleyecegiz
    ).points
    return hits


if __name__ == "__main__":
    import glob
    # repo'daki tum dosyalari ingest et
    lang_of = {".c": "c", ".py": "python", ".js": "javascript", ".java": "java"}
    all_chunks: list[Chunk] = []
    for path in glob.glob("repo/*"):
        ext = "." + path.rsplit(".", 1)[-1]
        if ext in lang_of:
            all_chunks += ingest(path, lang_of[ext])

    print(f"Toplam {len(all_chunks)} fonksiyon ingest edildi.\n")
    client = build_store(all_chunks)

    # Hedef: get_user'a en benzer fonksiyonlar
    target = next(c for c in all_chunks if c.func == "get_user")
    print(f"SORGU: '{target.func}' ({target.file}) fonksiyonuna en benzer 5:\n")
    for h in most_similar(client, target.code, k=5):
        p = h.payload
        if p["func"] == target.func and p["file"] == target.file:
            continue  # kendini atla
        print(f"  score={h.score:.3f}  {p['func']:<12} {p['file']:<12} "
              f"(satir {p['line_start']}-{p['line_end']}, cc={p['complexity']})")
