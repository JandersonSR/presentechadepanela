import streamlit as st
from pymongo import MongoClient, errors
from datetime import datetime
import unicodedata, re, os
from dotenv import load_dotenv
from bson import ObjectId

# ======================================================
# INIT
# ======================================================
load_dotenv()
st.set_page_config(page_title="Chá de Panela", page_icon="🎁", layout="wide")

# ======================================================
# FUNÇÕES
# ======================================================
def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z ]", "", texto)
    return texto.lower().strip()

def nome_valido(nome):
    partes = nome.strip().split()
    return len(partes) >= 2 and all(len(p) >= 2 for p in partes)

def gerar_user_id(nome):
    return f"user_{normalizar(nome).replace(' ', '_')}"

# ======================================================
# DB
# ======================================================
client = MongoClient(os.getenv("MONGO_URL"))
db = client["cha_panela"]
presentes_col = db["presentes"]
escolhas_col = db["escolhas"]

# índice concorrência
escolhas_col.create_index(
    [("user_id", 1), ("presente_id", 1)],
    unique=True
)

# ======================================================
# SESSION
# ======================================================
for k, v in {
    "admin": False,
    "user_id": None,
    "nome": None,
    "edit_item": None,
    "view_item": None
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ======================================================
# SIDEBAR
# ======================================================
modo = st.sidebar.radio("Acesso", ["🎁 Convidado", "🔐 Admin"])

# ======================================================
# ADMIN
# ======================================================
if modo == "🔐 Admin":

    if not st.session_state.admin:
        st.title("🔐 Login Admin")
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if u == os.getenv("ADMIN_USER") and s == os.getenv("ADMIN_PASSWORD"):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")
        st.stop()

    st.title("📊 Painel Administrativo")
    tab_p, tab_u = st.tabs(["📦 Presentes", "👥 Convidados"])

    # ================= PRESENTES =================
    with tab_p:
        st.subheader("➕ Novo presente")
        with st.form("novo"):
            nome = st.text_input("Nome")
            categoria = st.text_input("Categoria")
            qtd = st.number_input("Quantidade", 1, 100, 1)
            if st.form_submit_button("Salvar"):
                if nome:
                    presentes_col.insert_one({
                        "nome": nome.strip(),
                        "categoria": categoria.strip(),
                        "quantidade": qtd
                    })
                    st.rerun()

        st.divider()

        col1, col2 = st.columns(2)
        busca = col1.text_input("🔍 Buscar")
        filtro = col2.selectbox(
            "Filtro",
            ["Todos", "Escolhidos", "Não escolhidos", "Esgotados"]
        )

        for item in presentes_col.find().sort("categoria"):
            escolhidos = escolhas_col.count_documents({"presente_id": item["_id"]})

            if busca.lower() not in item["nome"].lower():
                continue
            if filtro == "Escolhidos" and escolhidos == 0:
                continue
            if filtro == "Não escolhidos" and escolhidos > 0:
                continue
            if filtro == "Esgotados" and item["quantidade"] > 0:
                continue

            st.markdown(f"### 🎁 {item['nome']}")
            st.write(f"Categoria: {item['categoria']}")
            st.write(f"Disponíveis: {item['quantidade']} | Escolhido: {escolhidos}")

            c1, c2, c3 = st.columns(3)
            if c1.button("👥 Convidados", key=f"v{item['_id']}"):
                st.session_state.view_item = item["_id"]
                st.session_state.edit_item = None
                st.rerun()
            if c2.button("✏️ Editar", key=f"e{item['_id']}"):
                st.session_state.edit_item = item["_id"]
                st.session_state.view_item = None
                st.rerun()
            if c3.button("🗑️ Excluir", key=f"d{item['_id']}"):
                escolhas_col.delete_many({"presente_id": item["_id"]})
                presentes_col.delete_one({"_id": item["_id"]})
                st.rerun()

        if st.session_state.edit_item:
            item = presentes_col.find_one({"_id": st.session_state.edit_item})
            st.divider()
            with st.form("editar"):
                n = st.text_input("Nome", item["nome"])
                q = st.number_input("Quantidade", 0, 100, item["quantidade"])
                if st.form_submit_button("Salvar"):
                    presentes_col.update_one(
                        {"_id": item["_id"]},
                        {"$set": {"nome": n, "quantidade": q}}
                    )
                    st.session_state.edit_item = None
                    st.rerun()

        if st.session_state.view_item:
            item = presentes_col.find_one({"_id": st.session_state.view_item})
            st.divider()
            for r in escolhas_col.find({"presente_id": item["_id"]}):
                c1, c2 = st.columns([4,1])
                c1.write(r["nome"])
                if c2.button("❌", key=str(r["_id"])):
                    escolhas_col.delete_one({"_id": r["_id"]})
                    presentes_col.update_one(
                        {"_id": item["_id"]},
                        {"$inc": {"quantidade": 1}}
                    )
                    st.rerun()

    # ================= CONVIDADOS =================
    with tab_u:
        for uid in escolhas_col.distinct("user_id"):
            regs = list(escolhas_col.find({"user_id": uid}))
            if not regs:
                continue
            with st.expander(regs[0]["nome"]):
                if st.button("🗑️ Excluir convidado", key=f"del{uid}"):
                    for r in regs:
                        presentes_col.update_one(
                            {"_id": r["presente_id"]},
                            {"$inc": {"quantidade": 1}}
                        )
                    escolhas_col.delete_many({"user_id": uid})
                    st.rerun()
                for r in regs:
                    p = presentes_col.find_one({"_id": r["presente_id"]})
                    c1, c2 = st.columns([4,1])
                    c1.write(p["nome"])
                    if c2.button("❌", key=str(r["_id"])):
                        escolhas_col.delete_one({"_id": r["_id"]})
                        presentes_col.update_one(
                            {"_id": p["_id"]},
                            {"$inc": {"quantidade": 1}}
                        )
                        st.rerun()

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if not st.session_state.user_id:
    st.title("🎁 Chá de Panela")
    nome = st.text_input("Nome e sobrenome")
    if st.button("Continuar"):
        if nome_valido(nome):
            st.session_state.nome = nome.strip()
            st.session_state.user_id = gerar_user_id(nome)
            st.rerun()
        else:
            st.error("Informe nome e sobrenome válidos")
    st.stop()

# ======================================================
# CONVIDADO
# ======================================================
tabs = st.tabs(["🎁 Escolher presentes", "📋 Meus presentes"])

with tabs[0]:
    busca = st.text_input("🔍 Buscar presente")
    categorias = ["Todas"] + sorted(presentes_col.distinct("categoria"))
    categoria = st.selectbox("Categoria", categorias)

    escolhas = list(escolhas_col.find({"user_id": st.session_state.user_id}))
    ids = [e["presente_id"] for e in escolhas]

    for item in presentes_col.find().sort("categoria"):
        if categoria != "Todas" and item["categoria"] != categoria:
            continue
        if busca.lower() not in item["nome"].lower():
            continue

        ja = item["_id"] in ids
        st.markdown(f"**🎁 {item['nome']}** ({item['categoria']}) — {item['quantidade']} disponíveis")

        if not ja and item["quantidade"] > 0:
            if st.button("Escolher", key=str(item["_id"])):
                try:
                    res = presentes_col.update_one(
                        {"_id": item["_id"], "quantidade": {"$gt": 0}},
                        {"$inc": {"quantidade": -1}}
                    )
                    if res.modified_count == 0:
                        st.warning("Acabou agora 😢")
                        st.rerun()

                    escolhas_col.insert_one({
                        "user_id": st.session_state.user_id,
                        "nome": st.session_state.nome,
                        "presente_id": item["_id"],
                        "data": datetime.utcnow()
                    })
                    st.rerun()
                except errors.DuplicateKeyError:
                    st.warning("Você já escolheu este presente")

with tabs[1]:
    for r in escolhas:
        p = presentes_col.find_one({"_id": r["presente_id"]})
        c1, c2 = st.columns([4,1])
        c1.write(p["nome"])
        if c2.button("❌ Remover", key=str(r["_id"])):
            escolhas_col.delete_one({"_id": r["_id"]})
            presentes_col.update_one(
                {"_id": p["_id"]},
                {"$inc": {"quantidade": 1}}
            )
            st.rerun()
