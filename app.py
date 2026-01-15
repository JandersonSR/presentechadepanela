import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata, re, os, json
from dotenv import load_dotenv
from streamlit_lottie import st_lottie

# ======================================================
# INIT
# ======================================================
load_dotenv()

st.set_page_config(
    page_title="Chá de Panela",
    page_icon="🎁",
    layout="wide"
)

# ======================================================
# FUNÇÕES
# ======================================================
def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z0-9 ]", "", texto)
    return texto.lower().strip()

def gerar_user_id(nome):
    return f"nome_{normalizar(nome).replace(' ', '')}"

def load_lottie(path):
    with open(path, "r") as f:
        return json.load(f)

# ======================================================
# CSS — MARKETPLACE PREMIUM
# ======================================================
st.markdown("""
<style>
:root {
    --marsala:#7A263A;
    --dark:#1f1f1f;
    --light:#ffffff;
}

.carousel {
    display:flex;
    gap:16px;
    overflow-x:auto;
    padding-bottom:10px;
}
.carousel::-webkit-scrollbar {
    height:6px;
}
.carousel::-webkit-scrollbar-thumb {
    background:var(--marsala);
    border-radius:10px;
}

.card {
    min-width:230px;
    padding:16px;
    border-radius:18px;
    background:var(--light);
    box-shadow:0 8px 18px rgba(0,0,0,.15);
    transition:.2s;
}
@media (prefers-color-scheme: dark){
    .card{background:var(--dark);color:#f2f2f2;}
}
.card:hover{transform:scale(1.04);}
.card.ja{border:2px solid var(--marsala);}

.badge{
    background:var(--marsala);
    color:white;
    padding:4px 10px;
    border-radius:14px;
    font-size:12px;
    display:inline-block;
    margin-top:6px;
}

.modal{
    position:fixed;
    inset:0;
    background:rgba(0,0,0,.55);
    display:flex;
    justify-content:center;
    align-items:center;
    z-index:9999;
}
.modal-box{
    background:white;
    padding:26px;
    border-radius:22px;
    width:420px;
}
@media (prefers-color-scheme: dark){
    .modal-box{background:#1f1f1f;color:white;}
}

button[kind="primary"]{
    background-color:var(--marsala)!important;
    border-radius:14px!important;
}
</style>
""", unsafe_allow_html=True)

# ======================================================
# DATABASE
# ======================================================
client = MongoClient(os.getenv("MONGO_URL"))
db = client["cha_panela"]
presentes_col = db["presentes"]
escolhas_col = db["escolhas"]

# ======================================================
# SESSION
# ======================================================
for k in ["user_id","nome","telefone","modal_item","show_lottie","admin"]:
    st.session_state.setdefault(k, None)

# ======================================================
# SIDEBAR
# ======================================================
modo = st.sidebar.radio("Acesso", ["🎁 Convidado", "🔐 Admin"])

# ======================================================
# ADMIN + ANALYTICS
# ======================================================
if modo == "🔐 Admin":

    if not st.session_state.admin:
        st.title("🔐 Login Admin")
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            if user == os.getenv("ADMIN_USER") and senha == os.getenv("ADMIN_PASSWORD"):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")
        st.stop()

    st.title("📊 Analytics — Chá de Panela")

    total_escolhas = escolhas_col.count_documents({})
    convidados = len(escolhas_col.distinct("user_id"))

    col1, col2 = st.columns(2)
    col1.metric("🎁 Total de escolhas", total_escolhas)
    col2.metric("👥 Convidados únicos", convidados)

    st.divider()

    # Ranking
    st.subheader("🥇 Presentes mais escolhidos")
    pipeline = [
        {"$group": {"_id": "$presente_id", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}}
    ]

    for r in escolhas_col.aggregate(pipeline):
        p = presentes_col.find_one({"_id": r["_id"]})
        st.write(f"**{p['nome']}** — {r['total']}x")

    st.divider()

    # Quem escolheu o quê
    st.subheader("📋 Quem escolheu o quê")

    filtro_presente = st.selectbox(
        "Filtrar por presente",
        ["Todos"] + [p["nome"] for p in presentes_col.find()]
    )

    for e in escolhas_col.find().sort("data", -1):
        p = presentes_col.find_one({"_id": e["presente_id"]})
        if filtro_presente != "Todos" and p["nome"] != filtro_presente:
            continue

        st.markdown(f"""
        <div class="card">
            <strong>{p['nome']}</strong><br>
            👤 {e.get('nome','')}<br>
            📞 {e.get('telefone','-')}<br>
            🕒 {e['data'].strftime('%d/%m %H:%M')}
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if not st.session_state.user_id:
    st.title("🎁 Chá de Panela")
    nome = st.text_input("Nome e sobrenome")
    telefone = st.text_input("Telefone (opcional)")

    if st.button("Continuar", type="primary"):
        if len(nome.split()) < 2:
            st.warning("Informe nome e sobrenome")
        else:
            st.session_state.nome = nome
            st.session_state.telefone = telefone or None
            st.session_state.user_id = gerar_user_id(nome)
            st.rerun()
    st.stop()

# ======================================================
# LOTTIE CONFIRMAÇÃO
# ======================================================
if st.session_state.show_lottie:
    lottie = load_lottie("lottie_success.json")
    st_lottie(lottie, height=250)
    st.session_state.show_lottie = None

# ======================================================
# MODAL
# ======================================================
if st.session_state.modal_item:
    item = presentes_col.find_one({"_id": st.session_state.modal_item})
    st.markdown("<div class='modal'><div class='modal-box'>", unsafe_allow_html=True)
    st.subheader("Confirmar presente 🎁")
    st.write(f"Você deseja escolher **{item['nome']}**?")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar", type="primary"):
            presentes_col.update_one({"_id": item["_id"]}, {"$inc": {"quantidade": -1}})
            escolhas_col.insert_one({
                "user_id": st.session_state.user_id,
                "nome": st.session_state.nome,
                "telefone": st.session_state.telefone,
                "presente_id": item["_id"],
                "data": datetime.utcnow()
            })
            st.session_state.modal_item = None
            st.session_state.show_lottie = True
            st.rerun()

    with c2:
        if st.button("Cancelar"):
            st.session_state.modal_item = None
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

# ======================================================
# UX PRINCIPAL
# ======================================================
escolhas = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids = [e["presente_id"] for e in escolhas]

st.markdown(f"### 🎁 Você escolheu **{len(ids)}** presentes")

for categoria in sorted(presentes_col.distinct("categoria")):
    st.subheader(f"📦 {categoria}")
    st.markdown("<div class='carousel'>", unsafe_allow_html=True)

    for item in presentes_col.find({"categoria": categoria}):
        ja = item["_id"] in ids

        st.markdown(
            f"""
            <div class="card {'ja' if ja else ''}">
                <strong>{item['nome']}</strong><br>
                <small>{item['quantidade']} disponíveis</small>
                {('<div class=badge>Já escolhido</div>' if ja else '')}
            </div>
            """,
            unsafe_allow_html=True
        )

        if not ja and item["quantidade"] > 0:
            if st.button("Selecionar", key=f"sel_{item['_id']}"):
                st.session_state.modal_item = item["_id"]
                st.rerun()

        if ja:
            if st.button("🔄 Trocar presente", key=f"troca_{item['_id']}"):
                escolhas_col.delete_one({
                    "user_id": st.session_state.user_id,
                    "presente_id": item["_id"]
                })
                presentes_col.update_one({"_id": item["_id"]}, {"$inc": {"quantidade": 1}})
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
