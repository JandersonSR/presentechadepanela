import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata
import re
import os
from dotenv import load_dotenv

# ======================================================
# CONFIG INICIAL
# ======================================================
load_dotenv()

st.set_page_config(
    page_title="Chá de Panela",
    page_icon="🎁",
    layout="wide"
)

# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================

def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z0-9 ]", "", texto)
    return texto.lower().strip()


def gerar_user_id(nome, telefone):
    if telefone:
        return f"tel_{telefone}"
    return f"nome_{normalizar(nome).replace(' ', '_')}"

# ======================================================
# CSS — UX DESKTOP FIRST
# ======================================================
st.markdown("""
<style>
body { background-color: #F6F1EE; }
h1, h2, h3, h4 { color: #7A263A; }

.card {
    background: white;
    padding: 14px;
    border-radius: 14px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    margin-bottom: 14px;
}

.card small { color: #555; }

.card.esgotado { opacity: 0.4; }
.card.ja-escolhido { border: 2px solid #7A263A; }

.badge {
    display: inline-block;
    background: #7A263A;
    color: white;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    margin-top: 6px;
}

button {
    background-color: #7A263A !important;
    color: white !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# ======================================================
# MONGODB
# ======================================================
client = MongoClient(os.getenv("MONGO_URL"))
db = client["cha_panela"]
presentes_col = db["presentes"]
escolhas_col = db["escolhas"]

# ======================================================
# SESSION STATE
# ======================================================
for key in ["user_id", "nome", "admin"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ======================================================
# SIDEBAR — LOGIN / ADMIN
# ======================================================
modo = st.sidebar.radio("Acesso", ["🎁 Convidado", "🔐 Admin"])

# ======================================================
# ADMIN
# ======================================================
if modo == "🔐 Admin":
    if not st.session_state.admin:
        st.sidebar.subheader("🔐 Login Admin")
        user = st.sidebar.text_input("Usuário")
        senha = st.sidebar.text_input("Senha", type="password")
        if st.sidebar.button("Entrar"):
            if user == os.getenv("ADMIN_USER") and senha == os.getenv("ADMIN_PASSWORD"):
                st.session_state.admin = True
                st.rerun()
            else:
                st.sidebar.error("Credenciais inválidas")
        st.stop()

    st.title("📊 Painel Administrativo")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🎁 Presentes")
        for p in presentes_col.find().sort("categoria"):
            escolhidos = escolhas_col.count_documents({"presente_id": p["_id"]})
            st.markdown(f"""
            <div class="card">
                <strong>{p['nome']}</strong><br>
                <small>{p['categoria']}</small><br>
                <b>Estoque:</b> {p['quantidade']} | <b>Escolhidos:</b> {escolhidos}
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.subheader("👥 Últimas escolhas")
        for e in escolhas_col.find().sort("data", -1).limit(10):
            presente = presentes_col.find_one({"_id": e["presente_id"]})
            st.markdown(f"""
            <div class="card">
                <strong>{presente['nome']}</strong><br>
                <small>{e['user_id']}<br>{e['data'].strftime('%d/%m %H:%M')}</small>
            </div>
            """, unsafe_allow_html=True)

    if st.sidebar.button("🚪 Sair"):
        st.session_state.admin = None
        st.rerun()

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if st.session_state.user_id is None:
    st.title("🎁 Chá de Panela")
    st.write("Informe seus dados para continuar 💕")

    nome = st.text_input("Nome completo *")
    telefone = st.text_input("Telefone (opcional)")

    if st.button("Continuar"):
        if len(nome.strip().split()) < 2:
            st.warning("Informe nome e sobrenome")
        else:
            telefone = re.sub(r"\D", "", telefone)
            st.session_state.user_id = gerar_user_id(nome, telefone)
            st.session_state.nome = nome
            st.rerun()

    st.stop()

# ======================================================
# APP PRINCIPAL — UX DESKTOP
# ======================================================
st.title("🎁 Escolha seus presentes")
st.write(f"Olá, **{st.session_state.nome}** 💖")

busca = st.text_input("🔎 Buscar presente")

escolhas_usuario = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids_escolhidos = [e["presente_id"] for e in escolhas_usuario]

query_busca = {}
if busca:
    query_busca["nome"] = {"$regex": busca, "$options": "i"}

# TABS
catalogo, meus_presentes = st.tabs(["🎁 Catálogo", "💝 Meus Presentes"])

with catalogo:
    for categoria in sorted(presentes_col.distinct("categoria")):
        st.subheader(categoria)

        itens = list(presentes_col.find({"categoria": categoria, **query_busca}))
        if not itens:
            continue

        cols = st.columns(3)

        for idx, item in enumerate(itens):
            col = cols[idx % 3]
            with col:
                ja_escolhido = item["_id"] in ids_escolhidos
                esgotado = item["quantidade"] <= 0

                st.markdown(f"""
                <div class="card {'ja-escolhido' if ja_escolhido else ''} {'esgotado' if esgotado else ''}">
                    <strong>{item['nome']}</strong><br>
                    <small>Restam {item['quantidade']}</small><br>
                    {"<span class='badge'>Já escolhido</span>" if ja_escolhido else ""}
                </div>
                """, unsafe_allow_html=True)

                if not esgotado and not ja_escolhido:
                    if st.button("Escolher 🎁", key=f"pick_{item['_id']}"):
                        presentes_col.update_one(
                            {"_id": item["_id"], "quantidade": {"$gt": 0}},
                            {"$inc": {"quantidade": -1}}
                        )
                        escolhas_col.insert_one({
                            "user_id": st.session_state.user_id,
                            "nome": normalizar(st.session_state.nome),
                            "presente_id": item["_id"],
                            "data": datetime.utcnow()
                        })
                        st.rerun()

with meus_presentes:
    if not escolhas_usuario:
        st.info("Você ainda não escolheu nenhum presente 💝")

    for e in escolhas_usuario:
        presente = presentes_col.find_one({"_id": e["presente_id"]})
        st.markdown(f"""
        <div class="card">
            <strong>{presente['nome']}</strong>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Trocar", key=f"swap_{e['_id']}"):
            presentes_col.update_one(
                {"_id": e["presente_id"]},
                {"$inc": {"quantidade": 1}}
            )
            escolhas_col.delete_one({"_id": e["_id"]})
            st.rerun()
