import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata
import re
import os
from dotenv import load_dotenv

load_dotenv()

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="🎁 Chá de Panela",
    page_icon="🎁",
    layout="wide"
)

# ======================================================
# CSS (FUNCIONA DE VERDADE)
# ======================================================
st.markdown("""
<style>

/* FUNDO */
.stApp {
    background-color: #F6F1EE;
}

/* CONTAINER */
[data-testid="stAppViewContainer"] {
    background-color: #F6F1EE;
}

/* CONTEÚDO */
[data-testid="stVerticalBlock"] {
    padding: 1.5rem 2.5rem;
}

/* CARD */
.card {
    background-color: #FFFFFF;
    border-radius: 16px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 8px 18px rgba(0,0,0,0.08);
}

/* CARD ESCOLHIDO */
.card.ja-escolhido {
    border: 2px solid #7A263A;
    background-color: #FFF7F9;
}

/* ESGOTADO */
.card.esgotado {
    opacity: 0.4;
}

/* TITULOS */
h1, h2, h3 {
    color: #7A263A;
}

/* BADGE */
.badge {
    display: inline-block;
    background-color: #7A263A;
    color: white;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11px;
    margin-top: 6px;
}

/* BOTÃO */
button[kind="primary"] {
    background-color: #7A263A !important;
    color: white !important;
    border-radius: 12px !important;
}

/* MOBILE */
@media (max-width: 900px) {
    [data-testid="stVerticalBlock"] {
        padding: 1rem;
    }
}

</style>
""", unsafe_allow_html=True)

# ======================================================
# HELPERS
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
# DB
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
        st.title("🔐 Admin")

        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            if user == os.getenv("ADMIN_USER") and senha == os.getenv("ADMIN_PASSWORD"):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")

        st.stop()

    st.title("📊 Painel Administrativo")

    st.subheader("🎁 Presentes")
    for p in presentes_col.find():
        escolhidos = escolhas_col.count_documents({"presente_id": p["_id"]})

        st.markdown(f"""
        <div class="card">
            <strong>{p['nome']}</strong><br>
            <small>{p['categoria']}</small><br>
            <b>Disponível:</b> {p['quantidade']} | <b>Escolhidos:</b> {escolhidos}
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("👥 Escolhas")

    for e in escolhas_col.find().sort("data", -1):
        presente = presentes_col.find_one({"_id": e["presente_id"]})

        st.markdown(f"""
        <div class="card">
            <strong>{presente['nome']}</strong><br>
            <small>{e['user_id']} • {e['data'].strftime('%d/%m/%Y %H:%M')}</small>
        </div>
        """, unsafe_allow_html=True)

        if st.button("❌ Remover", key=str(e["_id"])):
            presentes_col.update_one({"_id": e["presente_id"]}, {"$inc": {"quantidade": 1}})
            escolhas_col.delete_one({"_id": e["_id"]})
            st.rerun()

    if st.button("🚪 Sair"):
        st.session_state.admin = None
        st.rerun()

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if not st.session_state.user_id:
    st.title("🎁 Chá de Panela")
    st.write("Informe seus dados para continuar 💕")

    nome = st.text_input("Nome completo")
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
# LISTAGEM
# ======================================================
st.title("🎁 Escolha seus presentes")
st.write(f"Olá, **{st.session_state.nome}** 💖")

escolhas_usuario = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids_escolhidos = {e["presente_id"] for e in escolhas_usuario}

for categoria in sorted(presentes_col.distinct("categoria")):
    with st.expander(categoria, expanded=True):
        itens = list(presentes_col.find({"categoria": categoria}))

        col1, col2 = st.columns(2)

        for i, item in enumerate(itens):
            col = col1 if i % 2 == 0 else col2

            ja = item["_id"] in ids_escolhidos
            esgotado = item["quantidade"] <= 0

            with col:
                st.markdown(f"""
                <div class="card {'ja-escolhido' if ja else ''} {'esgotado' if esgotado else ''}">
                    <strong>{item['nome']}</strong><br>
                    <small>Disponível: {item['quantidade']}</small><br>
                    {("<span class='badge'>Já escolhido</span>" if ja else "")}
                </div>
                """, unsafe_allow_html=True)

                if not ja and not esgotado:
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

# ======================================================
# MEUS PRESENTES
# ======================================================
st.divider()
st.subheader("🎁 Meus presentes")

for e in escolhas_usuario:
    presente = presentes_col.find_one({"_id": e["presente_id"]})

    st.markdown(f"""
    <div class="card">
        <strong>{presente['nome']}</strong>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Trocar", key=f"swap_{e['_id']}"):
        presentes_col.update_one({"_id": e["presente_id"]}, {"$inc": {"quantidade": 1}})
        escolhas_col.delete_one({"_id": e["_id"]})
        st.rerun()
