import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata
import re
import os
from dotenv import load_dotenv

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
def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z0-9 ]", "", texto)
    return texto.lower().strip()

def gerar_user_id(nome, telefone):
    if telefone:
        return f"tel_{telefone}"
    return f"nome_{normalizar(nome).replace(' ', '')}"

# ======================================================
# CSS — DARK/LIGHT SAFE + MARKETPLACE UX
# ======================================================
st.markdown("""
<style>
:root {
    --marsala: #7A263A;
    --card-light: #ffffff;
    --card-dark: #1E1E1E;
    --text-light: #1c1c1c;
    --text-dark: #f2f2f2;
    --border-dark: #333;
}

body {
    background-color: transparent;
}

.card {
    background-color: var(--card-light);
    color: var(--text-light);
    padding: 18px;
    border-radius: 18px;
    margin-bottom: 16px;
    box-shadow: 0 8px 18px rgba(0,0,0,0.12);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    border: 1px solid #ddd;
}

@media (prefers-color-scheme: dark) {
    .card {
        background-color: var(--card-dark);
        color: var(--text-dark);
        border: 1px solid var(--border-dark);
    }
}

.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 14px 28px rgba(0,0,0,0.35);
}

.card.esgotado {
    opacity: 0.45;
}

.card.ja-escolhido {
    border: 2px solid var(--marsala);
}

.badge {
    display: inline-block;
    background-color: var(--marsala);
    color: white;
    padding: 4px 10px;
    border-radius: 14px;
    font-size: 12px;
    margin-top: 6px;
}

h1, h2, h3 {
    color: var(--marsala);
}

button[kind="primary"] {
    background-color: var(--marsala) !important;
    color: white !important;
    border-radius: 14px !important;
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
for key in ["user_id", "nome", "admin"]:
    st.session_state.setdefault(key, None)

# ======================================================
# SIDEBAR
# ======================================================
modo = st.sidebar.radio("Acesso", ["🎁 Convidado", "🔐 Admin"])

# ======================================================
# ADMIN
# ======================================================
if modo == "🔐 Admin":
    if not st.session_state.admin:
        st.subheader("🔐 Login Admin")

        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            if user == os.getenv("ADMIN_USER") and senha == os.getenv("ADMIN_PASSWORD"):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")

        st.stop()

    st.subheader("📊 Painel Administrativo")

     col1, col2 = st.columns([2, 1])

    with col1:
        for p in presentes_col.find():
            escolhidos = escolhas_col.count_documents({"presente_id": p["_id"]})
            st.markdown(f"""
            <div class="card">
                <strong>{p['nome']}</strong><br>
                <small>{p['categoria']}</small><br>
                <b>Disponível:</b> {p['quantidade']} |
                <b>Escolhidos:</b> {escolhidos}
            </div>
            """, unsafe_allow_html=True)

     with col2:
        st.subheader("👥 Escolhas")
        for e in escolhas_col.find().sort("data", -1):
            presente = presentes_col.find_one({"_id": e["presente_id"]})
            st.markdown(f"""
            <div class="card">
                <strong>{presente['nome']}</strong><br>
                <small>{e['user_id']}<br>{e['data'].strftime('%d/%m %H:%M')}</small>
            </div>
            """, unsafe_allow_html=True)

    if st.button("🚪 Sair"):
        st.session_state.admin = None
        st.rerun()

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if st.session_state.user_id is None:
    st.markdown("<h1>🎁 Chá de Panela</h1>", unsafe_allow_html=True)
    st.caption("Escolha seus presentes com carinho 💕")

    nome = st.text_input("Nome e sobrenome *")
    telefone = st.text_input("Telefone (sem DDD, opcional)")

    if st.button("Continuar", type="primary"):
        if len(nome.strip().split()) < 2:
            st.warning("Informe nome e sobrenome.")
        else:
            telefone = re.sub(r"\D", "", telefone)
            st.session_state.nome = nome
            st.session_state.user_id = gerar_user_id(nome, telefone)
            st.rerun()

    st.stop()

# ======================================================
# MARKETPLACE — AMAZON / IFOOD STYLE
# ======================================================
st.markdown("<h1>🎁 Escolha seus presentes</h1>", unsafe_allow_html=True)
st.caption(f"👤 {st.session_state.nome} • Você pode escolher mais de um presente")

busca = st.text_input("🔍 Buscar presente", placeholder="Ex: panela, copo, prato...")

escolhas_usuario = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids_escolhidos = [e["presente_id"] for e in escolhas_usuario]

categorias = sorted(presentes_col.distinct("categoria"))

for categoria in categorias:
    with st.expander(f"📦 {categoria}", expanded=False):
        itens = list(presentes_col.find({"categoria": categoria}))

        cols = st.columns(4)

        for idx, item in enumerate(itens):
            if busca and busca.lower() not in item["nome"].lower():
                continue

            col = cols[idx % 4]
            ja_escolhido = item["_id"] in ids_escolhidos
            esgotado = item["quantidade"] <= 0

            with col:
                st.markdown(f"""
                <div class="card {'ja-escolhido' if ja_escolhido else ''} {'esgotado' if esgotado else ''}">
                    <strong>{item['nome']}</strong><br>
                    <small>Disponível: {item['quantidade']}</small><br>
                    {("<span class='badge'>Já escolhido</span>" if ja_escolhido else "")}
                    {("<span class='badge'>Esgotado</span>" if esgotado else "")}
                </div>
                """, unsafe_allow_html=True)

                if not esgotado and not ja_escolhido:
                    if st.button("🎁 Escolher", key=f"pick_{item['_id']}", type="primary"):
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

# ======================================================
# MEUS PRESENTES
# ======================================================
st.markdown("---")
st.subheader("🎁 Meus presentes escolhidos")

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
