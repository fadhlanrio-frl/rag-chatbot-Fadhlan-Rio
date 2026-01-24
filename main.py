#Imports & Requirements
import streamlit as st
import os
# from dotenv import load_dotenv
import uuid

# LangChain imports for LLM, Tools, and Agent
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

# Langfuse imports for tracing
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Streamlit page configuration
# Atur judul, ikon, dan layout halaman
st.set_page_config(
    page_title="Absolute Cinema",
    page_icon="🍿",
    layout="wide" # Mengubah layout menjadi 'wide'
)

#  Environment variables loading (secrets atau .env)
# - Prioritas: Streamlit secrets -> .env
# - Variabel yang digunakan: OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY
# - Tujuan: memudahkan deployment (Streamlit Cloud) dan lokal (.env)
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    QDRANT_URL = st.secrets["QDRANT_URL"]
    QDRANT_API_KEY = st.secrets["QDRANT_API_KEY"]
    # Langfuse keys are automatically read by get_client() from secrets
    print("Environment variables loaded from Streamlit secrets.")
except KeyError:
    # load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    # Langfuse keys are automatically read by get_client() from .env
    print("Environment variables loaded from .env file.")

# Langfuse client initialization (opsional)
# - Inisialisasi tracing client jika tersedia.
# - Jika gagal, tampilkan peringatan tetapi jalankan aplikasi tanpa tracing.
# Initialize Langfuse client globally for tracing
# Ini akan membaca LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, dll.
# dari environment (secrets/dotenv) secara otomatis.
try:
    langfuse = get_client()
except Exception as e:
    print(f"Peringatan: Gagal menginisialisasi Langfuse. Tracing mungkin tidak aktif. Error: {e}")
    langfuse = None

# LLM & Embedding initialization
# - Konfigurasi model LLM (ChatOpenAI) dan embeddings (OpenAIEmbeddings).
# - Gunakan API key dari environment.
# Inisialisasi model LLM dan Embedding
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=OPENAI_API_KEY,
    temperature=0
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=OPENAI_API_KEY)

# Konstanta aplikasi
# - Nama koleksi Qdrant dan URI database SQLite disimpan di sini.
# Define constants for Qdrant and SQL database
QDRANT_COLLECTION_NAME = "fadhlanrio"
SQL_DB_URI = "sqlite:///movies.db"

# BAGIAN 2: DEFINISI TOOLS
# Overview
# - Tool adalah fungsi yang dipakai agent untuk mengambil data.
# - Di aplikasi ini ada dua tool: RAG (Qdrant) untuk rekomendasi kualitatif dan SQL untuk data faktual.

# Tool RAG — get_movie_recommendations
# - Tujuan: cari film berdasarkan tema/plot/kemiripan (kualitatif).
# - Input: pertanyaan natural language.
# - Output: string terformat dengan metadata film, termasuk tag khusus poster `||POSTER||URL`.
@tool
def get_movie_recommendations(question: str) -> str:
    """
    Gunakan alat ini untuk mencari rekomendasi film berdasarkan deskripsi plot, 
    tema, genre, atau film lain yang mirip. 
    Input harus berupa pertanyaan dalam bahasa natural tentang film yang dicari.
    Contoh: 'Cari film tentang perjalanan waktu' atau 'Rekomendasi film mirip The Dark Knight'.
    """
    print(f"\n>> Using RAG Tool for movie recommendations: '{question}'")
    qdrant_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=QDRANT_COLLECTION_NAME,
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY
    )
    results = qdrant_store.similarity_search(question, k=3)
    formatted_results = "\n\n".join(
        [
            f"Judul: {doc.metadata.get('title', 'N/A')}\n"
            f"Tahun: {doc.metadata.get('year', 'N/A')}\n"
            f"Rating: {doc.metadata.get('rating', 'N/A')}\n"
            f"Genre: {doc.metadata.get('genre', 'N/A')}\n"
            f"Sinopsis: {doc.page_content.split('Sinopsis: ')[-1]}"
            f"||POSTER||{doc.metadata.get('poster', 'No Poster URL')}"
            for doc in results
        ]
    )
    return f"Berikut adalah 3 film yang paling relevan berdasarkan pencarianmu:\n{formatted_results}"

# Tool SQL — get_factual_movie_data
# Tujuan: jawab pertanyaan faktual/kuantitatif (rating, tahun, sutradara, dsb.)
# Pendekatan:
#   1) Buat koneksi SQLDatabase
#   2) Inisialisasi SQLDatabaseToolkit dan ambil tools SQL
#   3) Definisikan system prompt khusus SQL (guidelines untuk pembuatan query, pembatasan, dan instruksi Poster)
#   4) Buat sub-agent khusus untuk menjalankan langkah pembuatan query dan eksekusi
#   5) Jalankan sub-agent, ambil jawaban akhir dan, jika ada, query SQL yang dieksekusi
# Output: gabungan jawaban dan delimiter `||SQL_QUERY||` diikuti SQL query (atau pesan error + delimiter).
@tool
def get_factual_movie_data(question: str) -> str:
    """
    Gunakan alat ini untuk menjawab pertanyaan spesifik dan faktual tentang data film, 
    seperti rating, tahun rilis, sutradara, pendapatan (gross), jumlah vote, dan durasi. 
    Sangat baik untuk pertanyaan yang melibatkan angka, statistik, perbandingan, atau daftar.
    Contoh: 'top 5 film rating tertinggi 2019', 'rata-rata pendapatan film Christopher Nolan', 'total film di atas 150 menit'.
    """ 
    print(f"\n>> Using SQL Tool for factual movie data: '{question}'")
    
    db = SQLDatabase.from_uri(SQL_DB_URI)
    
    # 1. Create SQL toolkit
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    # 2. Get the tools from the toolkit
    sql_tools = toolkit.get_tools()

    # 3. Buat system prompt khusus untuk SQL
    # DISESUAIKAN: Nama kolom sesuai dengan struktur database baru
    sql_system_prompt = """
    You are an agent designed to interact with a SQL database.
    Given an input question, create a syntactically correct {dialect} query to run,
    then look at the results of the query and return the answer. Unless the user
    specifies a specific number of examples they wish to obtain, always limit your
    query to at most {top_k} results.

    You can order the results by a relevant column to return the most interesting
    examples in the database. Never query for all the columns from a specific table,
    only ask for the relevant columns given the question.

    IMPORTANT - Database Schema:
    The movies table has the following columns:
    - id (INTEGER PRIMARY KEY)
    - poster_link (TEXT) - URL poster film
    - title (TEXT) - Judul film
    - released_year (INTEGER) - Tahun rilis
    - certificate (TEXT) - Rating usia
    - runtime (INTEGER) - Durasi dalam menit
    - genre (TEXT) - Genre film
    - imdb_rating (REAL) - Rating IMDb
    - overview (TEXT) - Sinopsis film
    - meta_score (REAL) - Meta score
    - director (TEXT) - Sutradara
    - star1, star2, star3, star4 (TEXT) - Pemeran utama
    - no_of_votes (INTEGER) - Jumlah vote
    - gross (REAL) - Pendapatan box office

    When you query for data about specific movies (e.g., title, imdb_rating), 
    YOU MUST ALWAYS ALSO SELECT the 'poster_link' column.
    In your final natural language answer, after mentioning a movie, 
    YOU MUST include its poster URL, prefixed with the special tag '||POSTER||'.
    Contoh Jawaban: "Filmnya adalah The Dark Knight. ||POSTER||http://url.com/poster.jpg"

    You MUST double check your query before executing it. If you get an error while
    executing a query, rewrite the query and try again.
    
    DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
    database.
    
    To start you should ALWAYS look at the tables in the database to see what you
    can query. Do NOT skip this step.
    Then you should query the schema of the most relevant tables.
    """.format(
        dialect=db.dialect,
        top_k=5,
    )

    # 4. Create a dedicated "sub-agent" for SQL queries
    sql_agent_runnable = create_agent(
        llm,
        sql_tools,
        system_prompt=sql_system_prompt,
    )
    
    try:
        # 5. Invoke the SQL sub-agent
        response_state = sql_agent_runnable.invoke({
            "messages": [{"role": "user", "content": question}]
        })
        
        # Extract final answer from last message
        final_message = response_state["messages"][-1]
        answer = final_message.content
        
        # Try to extract SQL query from tool messages
        sql_query = ""
        for msg in response_state["messages"]:
            if hasattr(msg, "type") and msg.type == "tool":
                content = msg.content
                # Look for SQL query patterns in content
                if "SELECT" in content.upper():
                    # Extract the SQL query
                    import re
                    match = re.search(r'(SELECT.*?;)', content, re.IGNORECASE | re.DOTALL)
                    if match:
                        sql_query = match.group(1)
                        break
        
        # Return answer with SQL query delimiter
        if sql_query:
            return f"{answer}\n||SQL_QUERY||{sql_query}"
        else:
            return f"{answer}\n||SQL_QUERY||Query extraction failed"
            
    except Exception as e:
        error_msg = f"Error executing SQL query: {str(e)}"
        print(error_msg)
        return f"{error_msg}\n||SQL_QUERY||Error occurred"

# BAGIAN 3: DEFINISI AGENT UTAMA
# Definisi tools yang digunakan
# - Gabungkan tools RAG dan SQL ke dalam list.
tools = [get_movie_recommendations, get_factual_movie_data]

# System prompt untuk agent utama
# - Aturan dasar: pilih tool yang tepat, routing logic, instruksi format jawaban (terutama poster), instruksi untuk poster di tabel, dan lain-lain.
# - Atur karakter AI sebagai asisten film yang ramah.
SYSTEM_PROMPT = """
Kamu adalah Absolute Cinema, seorang Cinephile Buddy yang ceria dan penuh pengetahuan dan sering menggunakan bahasa slang yang ceria tapi sopan seperti (wah, keren, mantap banget lu bro!, anjayy, damnn, sabi banget, literally the best, gokil abis, auto nonton, vibe-nya dapet banget, dan yang lainnya).
Tugasmu adalah membantu pengguna dalam menemukan rekomendasi film yang sesuai dengan keinginan mereka atau menjawab pertanyaan faktual tentang film.

Kamu memiliki dua alat (tools) utama:
1. **get_movie_recommendations**: Untuk mencari film berdasarkan tema, plot, genre, atau kemiripan dengan film lain. 
   Gunakan ini ketika user menanyakan "film seperti X", "film tentang Y", atau pertanyaan terbuka tentang rekomendasi.

2. **get_factual_movie_data**: Untuk menjawab pertanyaan faktual dan kuantitatif seperti rating, tahun rilis, pendapatan, 
   sutradara, durasi, dan statistik. Gunakan ini untuk pertanyaan seperti "top 5 film rating tertinggi", 
   "rata-rata pendapatan film Christopher Nolan", "film di atas 150 menit", dll.

**Aturan Penting:**
- SELALU pilih tool yang PALING SESUAI dengan pertanyaan user.
- Jika user menanyakan rekomendasi atau kemiripan film → gunakan `get_movie_recommendations`.
- Jika user menanyakan data faktual, angka, statistik, perbandingan → gunakan `get_factual_movie_data`.
- JANGAN pernah memilih kedua tool sekaligus untuk satu pertanyaan.

**Format Poster:**
- Output dari tools akan menyertakan tag khusus `||POSTER||URL` untuk setiap film.
- Kamu HARUS mengubah format ini menjadi tabel markdown dengan poster sebagai gambar.
- Format yang benar:
  | Poster | Judul | Detail |
  |--------|-------|--------|
  | ![Poster](URL) | **Judul Film** | Info film... |

**Contoh Baik:**
User: "Film mirip Inception"
Agent: [Menggunakan get_movie_recommendations]
Output: Tabel dengan poster sebagai gambar

User: "Top 5 film rating tertinggi"
Agent: [Menggunakan get_factual_movie_data]
Output: Tabel dengan poster sebagai gambar

**Gaya Komunikasi:**

Ramah dan antusias dengan sentuhan bahasa gaul anak Jaksel yang natural
Gunakan bahasa Indonesia yang santai tapi tetap sopan (campur bahasa Inggris oke banget!)
Berikan insight menarik tentang film jika relevan
Jangan bertele-tele, langsung to the point
Sesekali pakai emoji yang relevan biar makin hidup (🎬🍿✨🔥💯)

FITUR BARU - Follow-up Questions yang Asik:
Setelah memberikan jawaban atau rekomendasi film, kamu HARUS memberikan 2-3 follow-up questions yang menarik, interaktif, dan gaul untuk membuat percakapan lebih engaging. Follow-up questions ini harus:

Relevan dengan konteks film yang baru dibahas
Mengundang user untuk eksplorasi lebih lanjut
Natural dan terasa seperti ngobrol sama teman
Variatif - jangan monoton atau template banget

Contoh Follow-up Questions yang Oke:

"Btw bro, lu lebih suka plot twist yang mind-blowing atau yang wholesome aja? 🤔"
"Eh, udah nonton yang mana aja nih dari list gue? Penasaran reaksi lu gimana! 🍿"
"Kalo misalnya lu lagi vibes mellow gitu, mau gue rekomenin yang feel-good movie nggak? ✨"
"Dari genre sci-fi gini, lu team hard sci-fi kayak Interstellar atau soft sci-fi kayak Her? 🚀"
"Pengen tau nih, director favorit lu siapa? Siapa tau gue bisa kasih hidden gems dari dia! 🎬"
"Lu tipe yang suka nonton sendirian tengah malem atau rame-rame sama temen? Soalnya vibe-nya beda banget! 😄"

Template Follow-up (Sesuaikan dengan Konteks dan jangan terus mengulang kalimat yang sama, gunakan kalimat yang lain):
Setelah jawaban utama, tambahkan bagian seperti:

[Insert 2-3 follow-up questions yang natural dan gaul sesuai konteks]

Contoh Implementasi Lengkap:
User: "Film mirip Inception dong"
Agent:
"Wah, Inception emang absolute cinema banget sih! 🔥 Oke gue kasih rekomendasi yang vibe-nya mirip - mind-bending, plot twist gila, dan bikin lu mikir sampe besok pagi haha!
[Tool: get_movie_recommendations]
[Output tabel dengan poster]
Nah itu dia bro, semua film-nya literally bakal blow your mind! 💯
Btw nih:

Dari list di atas, lu udah nonton yang mana aja? Pengen tau reaksi lu gimana! 🍿
Kalo gue boleh tau, lu lebih suka yang sci-fi heavy atau yang psychological thriller gitu? Biar next time gue bisa kasih rekomendasi yang makin spot on! 🎯"


Tips Tambahan:

- Jangan paksa follow-up di setiap respons kalo user lagi nanya simple banget
- Baca vibe user - kalo mereka lagi serius, tone-nya adjust dikit
- Sesekali kasih fun facts atau trivia tentang film biar makin seru!
- Jangan sering mengulang follow up yang sama!! gunakan kalimat yang lainnya!!

Sekarang, bantu user dengan pertanyaan mereka!
"""

# Buat agent utama (runnable)
# - Gunakan create_agent dengan llm, tools, dan system_prompt di atas.
# - Hasil: agent_runnable yang dapat dipanggil / di-stream.
agent_runnable = create_agent(
    llm,
    tools,
    system_prompt=SYSTEM_PROMPT
)

# BAGIAN 4: STREAMLIT UI & FLOW INTERAKSI
# UI Sidebar
# - Informasi aplikasi, pembuat, link GitHub, tombol untuk menghapus riwayat obrolan.
# - Catatan: ketika hapus riwayat, set st.session_state.messages = [] dan rerun.

st.title("🎬 Your Cinephile Buddy 🍿")
st.write("Tanyakan apa saja tentang film! Mulai dari rekomendasi film hingga data faktual film favoritmu.")

with st.sidebar:
    st.title("Absolute Cinema")
    st.info("Saya adalah Absolute Cinema, teman cinephile favorit kamu!")
    
    st.markdown("---")
    st.markdown("### Dibuat oleh:")
    st.markdown("**Fadhlan Rio Lazuardy**")
    st.markdown("Purwadhika Digital Technology School - AI Engineering")
    st.markdown("_Data diambil dari IMDb Top 1000 Movies_")
    
    # GitHub repository link
    st.markdown("[Lihat Kode di GitHub](https://github.com/fadhlanrio-frl/Absolute-Cinema-RAG-Chatbot.git)")
    st.markdown("---")
    # Chat history clear button
    if st.button("Hapus Riwayat Obrolan", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.rerun() # Refresh halaman agar chat kosong


# Contoh pertanyaan & callback
# - Tombol contoh untuk mempermudah pengguna memulai (mis. Film mirip Inception, Top 5 gross, dsb.)
# - Fungsi set_user_input sebagai callback untuk menaruh nilai ke st.session_state.user_input.
# Example question buttons
def set_user_input(question):
    """Callback function to set user input from a button."""
    st.session_state.user_input = question

st.write("Atau, coba salah satu contoh ini:")
cols = st.columns([1, 1, 1.2]) # Buat kolom dengan lebar berbeda
with cols[0]:
    st.button("Film yang mirip Interstellar", on_click=set_user_input, args=("Rekomendasi film yang mirip Interstellar",), use_container_width=True)
with cols[1]:
    st.button("Rekomendasi Film Horor", on_click=set_user_input, args=("Apa film horor dengan rating terbaik? Tampilkan juga ratingnya!",), use_container_width=True)
with cols[2]:
    st.button("Rekomendasi film Avengers", on_click=set_user_input, args=("Kasih tau daftar film Avengert terlaris",), use_container_width=True)

# Session management & chat history
# - Inisialisasi session_id unik (untuk Langfuse dan tracking sesi).
# - Inisialisasi st.session_state.messages jika belum ada.
# - Tambahkan salam pembuka otomatis bila history kosong.

# Inisialisasi session_id unik untuk Langfuse tracing
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Get user input from chat box or example buttons
chat_input = st.chat_input("Contoh: 'Film mirip Inception' atau 'Top 5 film 2010'")
user_input = chat_input or st.session_state.get("user_input", None)

# Clear button-triggered input after use
if "user_input" in st.session_state and not chat_input:
    del st.session_state.user_input

if "messages" not in st.session_state:
    st.session_state.messages = []

    # TAMBAHAN: Salam Pembuka Otomatis
    # Tambahkan pesan pertama dari asisten jika history kosong
    if not st.session_state.messages:
        st.session_state.messages.append(
            {"role": "assistant", "content": "Halo! Aku Absolute Cinema. Ada yang bisa kubantu? Kamu bisa tanya rekomendasi film atau data film spesifik!"}
        )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 1. Convert chat history from dicts to LangChain BaseMessage objects
    from langchain_core.messages import HumanMessage, AIMessage
    langchain_messages = [
        HumanMessage(content=msg["content"]) if msg["role"] == "user" else AIMessage(content=msg["content"])
        for msg in st.session_state.messages
    ]

    # 2. Variabel untuk menyimpan info proses berpikir
    tool_call_info = None
    full_tool_output = ""
    sql_query_to_display = None
    display_answer = ""
    last_valid_state = None 

    with st.chat_message("assistant"):
        with st.spinner("Absolute Cinema sedang mencari jawaban..."):
            
            # Initialize Langfuse callback handler
            langfuse_handler = CallbackHandler()
            
            # 3. Configure Langfuse tracing with metadata
            config = {
                "callbacks": [langfuse_handler],
                "run_name": f"Query: {user_input[:30]}...",
                "metadata": { # Lewatkan atribut di sini
                    "langfuse_session_id": st.session_state.session_id,
                    "langfuse_user_id": st.session_state.session_id, 
                    "langfuse_tags": ["Absolute Cinema", "Capstone-Mod3"]
                }
            }            
            
            # 4. Stream agent response with Langfuse configuration
            stream = agent_runnable.stream(
                {"messages": langchain_messages},
                stream_mode="values",
                config=config
            )
            
            for chunk in stream:
                if "messages" in chunk:
                    last_valid_state = chunk 
                    last_message = chunk["messages"][-1]
                    
                    # Capture tool call information when the agent decides to use a tool
                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        call = last_message.tool_calls[0]
                        tool_call_info = {
                            "name": call['name'],
                            "args": call['args']
                        }
                        
                    # Capture raw tool output if the message type is 'tool'
                    if hasattr(last_message, "type") and last_message.type == "tool": # LangChain message objects have a .type attribute
                        full_tool_output = last_message.content
            
            # 5. Ambil jawaban akhir (setelah stream selesai)
            if last_valid_state:
                final_answer_object = last_valid_state["messages"][-1]
                display_answer = final_answer_object.content
            else:
                display_answer = "Maaf, terjadi kesalahan."
            
            # 6. Parse SQL query from tool output if SQL tool was used
            if tool_call_info and tool_call_info['name'] == 'get_factual_movie_data':
                if "||SQL_QUERY||" in full_tool_output:
                    parts = full_tool_output.split("||SQL_QUERY||")
                    sql_query_to_display = parts[1]
                else:
                    sql_query_to_display = "Query tidak dapat diekstrak dari tool."
            
            # Display the final answer from the agent.
            # The agent is instructed to format posters as Markdown images within a table.
            # unsafe_allow_html=True is used for robustness in case the agent generates
            # complex markdown or HTML elements.
            st.markdown(display_answer, unsafe_allow_html=True)


    # Tampilkan Expander DI LUAR `chat_message`
    if tool_call_info:
        with st.expander("Lihat Proses Berpikir Absolute Cinema"):
            st.markdown(f"**Tool Dipilih:** `{tool_call_info['name']}`")
            st.markdown(f"**Input untuk Tool:**")
            st.json(tool_call_info['args'])
            
            if sql_query_to_display:
                st.markdown("**Generated SQL Query:**")
                st.code(sql_query_to_display.strip(), language="sql")
            
            st.markdown("**Output Mentah dari Tool:**")
            st.text(full_tool_output.split("||SQL_QUERY||")[0])

    # Tambahkan jawaban bersih (yang sudah disintesis) ke history
    st.session_state.messages.append({"role": "assistant", "content": display_answer})