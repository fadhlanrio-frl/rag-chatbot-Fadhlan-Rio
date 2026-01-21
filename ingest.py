import pandas as pd
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

# config
QDRANT_URL = "https://e1b92f8f-0452-479e-98b2-8897c5100ac6.europe-west3-0.gcp.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.G-kzR-BBjAMSjrLr16N-2ALhiXjaeUFxio1IcY4xnIA"
COLLECTION_NAME = "fadhlanrio"

# load dataset
df = pd.read_csv("data/imdb_top_1000_cleaned.csv")


# convert to Document
docs = []
for _, row in df.iterrows():
    content = f"""
    Title: {row['Series_Title']}
    Overview: {row['Overview']}
    Genre: {row['Genre']}
    """
    docs.append(
        Document(
            page_content=content,
            metadata={
                'title': row['Series_Title'],
                'year': row['Released_Year'],
                'rating': row['IMDB_Rating'],
                'genre': row['Genre'],
                'poster': row['Poster_Link']
            }
        )
    )

# embedding
embeddings = OpenAIEmbeddings()

docs = docs[:100]

# upload ke Qdrant (INI YANG PENTING)
QdrantVectorStore.from_documents(
    documents=docs,
    embedding=embeddings,
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    collection_name=COLLECTION_NAME
)

print("✅ Dataset berhasil di-ingest ke Qdrant")
