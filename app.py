import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata
import re
import os
from dotenv import load_dotenv

load_dotenv()

# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================
def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z0-9]", "", texto)
    return texto.lower()

def gerar_user_id(nome, telefone):
    if telefone:
        return f"tel_{telefone}"
    return f"nome_{normalizar(nome)}"

# ======================================================
# CONFIGURAÇÃO
# ======================================================
st.set_page_config(
    page_title="Chá de Panela",
    page_icon="🎁",
    layout="centered"
)

# ======================================================
# CSS — MARSALA
# ======================================================
st.markdown("""
<style>
body { background-color: #F6F1EE; }
h1, h2, h3 { color: #7A263A; }
.card {
    background: white;
    padding: 16px;
    border-radius: 16px;
    margin-bottom: 12px;
    box-shadow: 0 6px 14px rgba(0,0,0,0.08);
}
.card.esgotado { opacity: 0.45; }
.card.ja-escolhido { border: 2px solid #7A263A; }
.badge {
    background: #7A263A;
    color: white;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
}
button {
    background-color: #7A263A !important;
    color: white !important;
    border-radius: 12px !important;
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
# MENU SUPERIOR
# ======================================================
modo = st.sidebar.radio(
    "Acesso",
    ["🎁 Convidado", "🔐 Admin"]
)

# ======================================================
# LOGIN ADMIN
# ======================================================
if modo == "🔐 Admin":
    if not st.session_state.admin:
        st.subheader("🔐 Acesso Administrativo")

        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            if (
                user == os.getenv("ADMIN_USER")
                and senha == os.getenv("ADMIN_PASSWORD")
            ):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")

        st.stop()

    # ==================================================
    # PAINEL ADMIN
    # ==================================================
    st.subheader("📊 Painel Administrativo")

    st.markdown("### 🎁 Presentes e Estoque")
    for p in presentes_col.find():
        total_escolhido = escolhas_col.count_documents(
            {"presente_id": p["_id"]}
        )

        st.markdown(f"""
        <div class="card">
            <strong>{p['nome']}</strong><br>
            <small>{p['categoria']} • </small><br>
            <b>Restam:</b> {p['quantidade']} |
            <b>Escolhidos:</b> {total_escolhido}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 👥 Escolhas dos Convidados")

    escolhas = list(escolhas_col.find().sort("data", -1))

    for e in escolhas:
        presente = presentes_col.find_one({"_id": e["presente_id"]})

        st.markdown(f"""
        <div class="card">
            <strong>{presente['nome']}</strong><br>
            <small>
                Convidado: {e['user_id']}<br>
                Data: {e['data'].strftime('%d/%m/%Y %H:%M')}
            </small>
        </div>
        """, unsafe_allow_html=True)

        if st.button("❌ Remover escolha", key=f"del_{e['_id']}"):
            presentes_col.update_one(
                {"_id": e["presente_id"]},
                {"$inc": {"quantidade": 1}}
            )
            escolhas_col.delete_one({"_id": e["_id"]})
            st.rerun()

    if st.button("🚪 Sair do admin"):
        st.session_state.admin = None
        st.rerun()

    st.stop()

# ======================================================
# MODO CONVIDADO (APP PRINCIPAL)
# ======================================================
# (mantém exatamente o fluxo que você já aprovou)

if st.session_state.user_id is None:
    st.markdown("<h1>🎁 Chá de Panela</h1>", unsafe_allow_html=True)
    st.write("Informe seus dados para continuar 💕")

    nome = st.text_input("Nome e sobrenome *")
    telefone = st.text_input("Telefone (sem DDD, opcional)")

    if st.button("Continuar"):
        if not nome.strip() or len(nome.strip().split()) < 2:
            st.warning("Informe nome e sobrenome.")
        else:
            telefone = re.sub(r"\D", "", telefone)
            st.session_state.user_id = gerar_user_id(nome, telefone)
            st.session_state.nome = nome
            st.rerun()

    st.stop()

# ======================================================
# LISTAGEM CONVIDADO
# ======================================================
st.markdown("<h1>🎁 Escolha seus presentes</h1>", unsafe_allow_html=True)
st.write(f"Olá, **{st.session_state.nome}** 💖")

escolhas_usuario = list(
    escolhas_col.find({"user_id": st.session_state.user_id})
)
ids_escolhidos = [e["presente_id"] for e in escolhas_usuario]

for categoria in sorted(presentes_col.distinct("categoria")):
    st.markdown(f"### {categoria}")

    for item in presentes_col.find({"categoria": categoria}):
        ja_escolhido = item["_id"] in ids_escolhidos
        esgotado = item["quantidade"] <= 0

        st.markdown(f"""
        <div class="card {'ja-escolhido' if ja_escolhido else ''}">
            <strong>{item['nome']}</strong><br>
            <small>• Restam {item['quantidade']}</small><br>
            {("<span class='badge'>Já escolhido</span>" if ja_escolhido else "")}
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

st.markdown("---")
st.subheader("🎁 Meus presentes")

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
