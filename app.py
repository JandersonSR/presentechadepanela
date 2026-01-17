import streamlit as st
from pymongo import MongoClient, errors
from datetime import datetime
import unicodedata, re, os
from dotenv import load_dotenv
from bson import ObjectId
from collections import defaultdict

# ======================================================
# INIT
# ======================================================
load_dotenv()
st.set_page_config(page_title="Chá de Panela", page_icon="🎁", layout="wide")

# ======================================================
# FUNÇÕES
# ======================================================
def normalizar(txt):
    txt = unicodedata.normalize("NFD", txt)
    txt = txt.encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-zA-Z ]", "", txt).lower().strip()

def nome_valido(nome):
    p = nome.strip().split()
    return len(p) >= 2 and all(len(x) >= 2 for x in p)

def gerar_user_id(nome):
    return f"user_{normalizar(nome).replace(' ', '_')}"

# ======================================================
# DATABASE
# ======================================================
client = MongoClient(os.getenv("MONGO_URL"))
db = client["cha_panela"]
presentes_col = db["presentes"]
escolhas_col = db["escolhas"]

try:
    escolhas_col.create_index(
        [("user_id", 1), ("presente_id", 1)], unique=True
    )
except:
    pass

# ======================================================
# SESSION
# ======================================================
for k in ["admin", "user_id", "nome", "edit_item", "view_item"]:
    st.session_state.setdefault(k, None)

st.session_state.setdefault("admin", False)

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

        with st.form("novo_presente"):
            st.subheader("➕ Novo presente")
            nome = st.text_input("Nome")
            categoria = st.text_input("Categoria")
            qtd = st.number_input("Quantidade", 1, 100, 1)
            if st.form_submit_button("Salvar"):
                presentes_col.insert_one({
                    "nome": nome.strip(),
                    "categoria": categoria.strip(),
                    "quantidade": qtd
                })
                st.rerun()

        busca = st.text_input("🔍 Buscar presente")
        filtro = st.selectbox(
            "Filtro",
            ["Todos", "Escolhidos", "Não escolhidos", "Esgotados"]
        )

        # -------- AGRUPAMENTO
        grupos = defaultdict(list)
        for p in presentes_col.find():
            grupos[p["categoria"] or "Sem categoria"].append(p)

        for categoria, itens in sorted(grupos.items()):
            with st.expander(f"📂 {categoria}", expanded=True):

                for item in itens:
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
                    st.write(f"Disponíveis: {item['quantidade']} | Escolhido: {escolhidos}")

                    c1, c2, c3 = st.columns(3)
                    if c1.button("👥", key=f"adm_view_{item['_id']}"):
                        st.session_state.view_item = item["_id"]
                        st.session_state.edit_item = None
                        st.rerun()

                    if c2.button("✏️", key=f"adm_edit_{item['_id']}"):
                        st.session_state.edit_item = item["_id"]
                        st.session_state.view_item = None
                        st.rerun()

                    if c3.button("🗑️", key=f"adm_del_{item['_id']}"):
                        escolhas_col.delete_many({"presente_id": item["_id"]})
                        presentes_col.delete_one({"_id": item["_id"]})
                        st.rerun()

        # ---- CONVIDADOS DO ITEM
        if st.session_state.view_item:
            item = presentes_col.find_one({"_id": st.session_state.view_item})
            st.divider()
            st.subheader(f"👥 Convidados – {item['nome']}")

            for r in escolhas_col.find({"presente_id": item["_id"]}):
                c1, c2 = st.columns([4,1])
                c1.write(r["nome"])
                if c2.button("❌", key=f"adm_item_user_del_{r['_id']}"):
                    escolhas_col.delete_one({"_id": r["_id"]})
                    presentes_col.update_one(
                        {"_id": item["_id"]}, {"$inc": {"quantidade": 1}}
                    )
                    st.rerun()

    # ================= CONVIDADOS =================
    with tab_u:
        for uid in escolhas_col.distinct("user_id"):
            regs = list(escolhas_col.find({"user_id": uid}))
            if not regs:
                continue

            with st.expander(regs[0]["nome"]):
                for r in regs:
                    p = presentes_col.find_one({"_id": r["presente_id"]})
                    c1, c2 = st.columns([4,1])
                    c1.write(p["nome"])
                    if c2.button("❌", key=f"adm_user_item_del_{r['_id']}"):
                        escolhas_col.delete_one({"_id": r["_id"]})
                        presentes_col.update_one(
                            {"_id": p["_id"]}, {"$inc": {"quantidade": 1}}
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
            st.session_state.nome = nome
            st.session_state.user_id = gerar_user_id(nome)
            st.rerun()
        else:
            st.error("Informe nome e sobrenome válidos")
    st.stop()

# ======================================================
# CONVIDADO
# ======================================================
busca = st.text_input("🔍 Buscar presente")

escolhidos = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids = [e["presente_id"] for e in escolhidos]

grupos = defaultdict(list)
for p in presentes_col.find():
    grupos[p["categoria"] or "Sem categoria"].append(p)

for categoria, itens in sorted(grupos.items()):
    with st.expander(f"📂 {categoria}", expanded=True):

        for item in itens:
            if busca.lower() not in item["nome"].lower():
                continue

            ja = item["_id"] in ids
            st.markdown(
                f"**🎁 {item['nome']}** — {item['quantidade']} disponíveis"
                + (" ✅ escolhido" if ja else "")
            )

            if not ja and item["quantidade"] > 0:
                if st.button("Escolher", key=f"user_choose_{item['_id']}"):
                    try:
                        res = presentes_col.update_one(
                            {"_id": item["_id"], "quantidade": {"$gt": 0}},
                            {"$inc": {"quantidade": -1}}
                        )
                        if res.modified_count == 0:
                            st.warning("Esse presente acabou agora 😢")
                            st.rerun()

                        escolhas_col.insert_one({
                            "user_id": st.session_state.user_id,
                            "nome": st.session_state.nome,
                            "presente_id": item["_id"],
                            "data": datetime.utcnow()
                        })
                        st.rerun()
                    except errors.DuplicateKeyError:
                        st.warning("Você já escolheu esse presente")
