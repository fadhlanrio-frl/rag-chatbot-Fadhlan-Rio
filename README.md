# 🎬 Absolute Cinema – Movie Expert  
**Retrieval-Augmented Generation (RAG) Chatbot untuk Rekomendasi & Informasi Film**

---

## 📌 Deskripsi Proyek
Project ini merupakan implementasi **RAG (Retrieval-Augmented Generation) Chatbot** yang berfungsi sebagai **Movie Expert Assistant**.  
Chatbot mampu menjawab pertanyaan seputar film dengan memanfaatkan **retrieval berbasis vektor** dan **Large Language Model (LLM)** sehingga jawaban yang diberikan lebih kontekstual, relevan, dan akurat.

Project ini dikembangkan sebagai **tugas akademik**, dengan fokus pada penerapan konsep RAG, integrasi LLM, serta pengelolaan dependensi yang baik menggunakan **Poetry**.

---

## 🧠 Konsep RAG yang Digunakan
Alur kerja chatbot:

1. **User Query**  
   Pengguna mengajukan pertanyaan terkait film.
2. **Retrieval**  
   Sistem mengambil data relevan dari knowledge base berbasis vektor.
3. **Augmentation**  
   Informasi hasil retrieval digabungkan dengan prompt.
4. **Generation**  
   LLM menghasilkan jawaban berbasis konteks yang diperoleh.

---

## 🛠️ Teknologi yang Digunakan
- **Python 3**
- **Streamlit** – antarmuka web interaktif
- **LangChain** – orkestrasi RAG
- **OpenAI API** – language model
- **Qdrant** – vector database
- **SQLAlchemy** – pengelolaan database
- **Poetry** – dependency & environment management

---

## 📂 Struktur Proyek
```text
.
├── main.py                     # Entry point aplikasi Streamlit
├── data/                        # Dataset & knowledge base
├── imdb_dataset_loading_&_preprocessing.ipynb
├── requirements.txt
├── pyproject.toml
├── poetry.lock
├── README.md
└── setup.py



