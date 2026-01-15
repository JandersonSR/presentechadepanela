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
# CSS — UX PROFISSIONAL (DARK/LIGHT SAFE)
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

.card {
    background-color: var(--card-light);
    color: var(--text-light);
    padding: 18px;
    border-radius: 18px;
    box-shadow: 0 8px 18px rgba(0,0,0,0.12);
    border: 1px solid #ddd;
    cursor: pointer;
    transition: all 0.15s ease;
    margin-bottom: 14px;
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

.card.esgotado { opacity: 0.45; }
.card.ja-escolhido { border: 2px solid var(--marsala); }

.badge {
    background-color: var(--marsala);
    color: white;
    padding: 4px 10px;
    border-radius: 14px;
    font-size: 12px;
    display: inline-block;
    margin-top: 6px;
}

.indicador {
    position: sticky;
    top: 0;
    z-index: 999;
    background: rgba(255,255,255,0.85);
    padding: 10px;
    border-radius: 12px;
    margin-bottom: 12px;
}

@media (prefers-color-scheme: dark) {
    .indicador {
        background: rgba(30,30,30,0.9);
    }
}

button[kind="primary"] {
    background-color: var(--marsala) !important;
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

    st.title("📊 Painel Administrativo")

    tab1, tab2, tab3 = st.tabs(["👥 Escolhas", "🎁 Itens", "➕ Criar / Editar"])

    # ---------- TAB ESCOLHAS ----------
    with tab1:
        for e in escolhas_col.find().sort("data", -1):
            presente = presentes_col.find_one({"_id": e["presente_id"]})
            st.markdown(f"""
            <div class="card">
                <strong>{presente['nome']}</strong><br>
                <small>{e['user_id']} • {e['data'].strftime('%d/%m %H:%M')}</small>
            </div>
            """, unsafe_allow_html=True)

            if st.button("❌ Remover escolha", key=f"del_{e['_id']}"):
                presentes_col.update_one({"_id": e["presente_id"]}, {"$inc": {"quantidade": 1}})
                escolhas_col.delete_one({"_id": e["_id"]})
                st.rerun()

    # ---------- TAB ITENS ----------
    with tab2:
        for p in presentes_col.find():
            escolhidos = escolhas_col.count_documents({"presente_id": p["_id"]})
            st.markdown(f"""
            <div class="card">
                <strong>{p['nome']}</strong><br>
                <small>{p['categoria']}</small><br>
                Disponível: {p['quantidade']} | Escolhidos: {escolhidos}
            </div>
            """, unsafe_allow_html=True)

    # ---------- TAB CRUD ----------
    with tab3:
        st.subheader("Criar / Editar Item")

        itens = list(presentes_col.find())
        item_sel = st.selectbox(
            "Editar item existente",
            ["NOVO"] + [i["_id"] for i in itens]
        )

        if item_sel != "NOVO":
            item = presentes_col.find_one({"_id": item_sel})
        else:
            item = {"_id": "", "nome": "", "categoria": "", "quantidade": 1}

        _id = st.text_input("ID", item["_id"])
        nome = st.text_input("Nome", item["nome"])
        categoria = st.text_input("Categoria", item["categoria"])
        quantidade = st.number_input("Quantidade", min_value=0, value=item["quantidade"])

        if st.button("💾 Salvar"):
            presentes_col.update_one(
                {"_id": _id},
                {"$set": {
                    "_id": _id,
                    "nome": nome,
                    "categoria": categoria,
                    "quantidade": quantidade
                }},
                upsert=True
            )
            st.success("Item salvo com sucesso")
            st.rerun()

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if st.session_state.user_id is None:
    st.title("🎁 Chá de Panela")
    nome = st.text_input("Nome e sobrenome")
    telefone = st.text_input("Telefone (opcional)")

    if st.button("Continuar", type="primary"):
        if len(nome.split()) < 2:
            st.warning("Informe nome e sobrenome")
        else:
            st.session_state.nome = nome
            st.session_state.user_id = gerar_user_id(nome, telefone)
            st.rerun()
    st.stop()

# ======================================================
# CONVIDADO UX
# ======================================================
escolhas_usuario = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids_escolhidos = [e["presente_id"] for e in escolhas_usuario]

st.markdown(f"""
<div class="indicador">
🎁 Você escolheu <strong>{len(ids_escolhidos)}</strong> presentes
</div>
""", unsafe_allow_html=True)

busca = st.text_input("🔍 Buscar presente")

for categoria in sorted(presentes_col.distinct("categoria")):
    with st.expander(f"📦 {categoria}", expanded=False):
        cols = st.columns(4)
        for i, item in enumerate(presentes_col.find({"categoria": categoria})):
            if busca and busca.lower() not in item["nome"].lower():
                continue

            col = cols[i % 4]
            ja = item["_id"] in ids_escolhidos
            esgotado = item["quantidade"] <= 0

            with col:
                if st.button(
                    f"{item['nome']} • {item['quantidade']} disponíveis",
                    key=f"card_{item['_id']}",
                    disabled=esgotado or ja
                ):
                    presentes_col.update_one({"_id": item["_id"]}, {"$inc": {"quantidade": -1}})
                    escolhas_col.insert_one({
                        "user_id": st.session_state.user_id,
                        "presente_id": item["_id"],
                        "data": datetime.utcnow()
                    })
                    st.rerun()
