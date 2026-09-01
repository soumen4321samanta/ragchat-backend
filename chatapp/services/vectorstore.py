"""
Wraps sentence-transformers (embeddings) + ChromaDB (vector storage).
Both run 100% locally -- no API cost.
"""
import chromadb
from django.conf import settings
from sentence_transformers import SentenceTransformer

_embedder = None
_chroma_client = None


def get_embedder():
    """Lazy-load the embedding model once and reuse it (it's ~90MB)."""
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _embedder


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    return model.encode(texts, show_progress_bar=False).tolist()


def add_chunks_to_collection(collection_name: str, chunks: list[str], metadatas: list[dict]):
    """Embed chunks and store them in a Chroma collection."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=collection_name)

    embeddings = embed_texts(chunks)
    ids = [f"{collection_name}_{i}" for i in range(len(chunks))]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return len(chunks)


def query_collections(collection_names: list[str], query_text: str, top_k: int = 4):
    """
    Search one or more Chroma collections for the chunks most similar
    to the query, and return the best `top_k` merged across all of them.
    """
    client = get_chroma_client()
    query_embedding = embed_texts([query_text])[0]

    results = []
    for name in collection_names:
        try:
            collection = client.get_collection(name=name)
        except Exception:
            continue  # collection might not exist yet

        res = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        docs = res.get('documents', [[]])[0]
        metas = res.get('metadatas', [[]])[0]
        dists = res.get('distances', [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            results.append({'text': doc, 'metadata': meta, 'distance': dist})

    # Lower distance = more similar. Sort and keep the overall best top_k.
    results.sort(key=lambda r: r['distance'])
    return results[:top_k]


def delete_collection(collection_name: str):
    client = get_chroma_client()
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass


def get_all_chunks(collection_name:str)->list[str]:

    """
    Fetch every chunk stored for a document, in original order.
    Unlike query_collections(), this does not embed or sort by similarity.
    it just returns the raw chunks in the order they were added to the collection.  

    """

    client=get_chroma_client()
    try:
        collection=client.get_collection(name=collection_name)
    except Exception:
        return[]


    result=collection.get()  # returns everything in the collection
    documents=result.get('documents',[])
    metadatas=result.get('metadatas',[])

    # Sort by the 'chunk_index' in metadata to restore original order
    paired=sorted(
        zip(documents,metadatas),
        key=lambda pair:pair[1].get('chunk_index',0)
    )
    return [doc for doc, meta in paired]
