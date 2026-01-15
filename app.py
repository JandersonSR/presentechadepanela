import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata, re, os
from dotenv import load_dotenv
from bson import ObjectId

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

# ======================================================
# CSS
# ======================================================
st.markdown("""
<style>
:root { --marsala:#7A263A; }

.card {
    padding:16px;
    border-radius:16px;
    background:rgba(255,255,255,.96);
    box-shadow:0 6px 16px rgba(0,0,0,.12);
    margin-bottom:14px;
}

@media (prefers-color-scheme: dark){
    .card{background:#1f1f1f;color:#f2f2f2;}
}

.card.ja { border:2px solid var(--marsala); }

.badge {
    background:var(--marsala);
    color:white;
    padding:4px 10px;
    border-radius:14px;
    font-size:12px;
    display:inline-block;
    margin-top:6px;
}

img.presente {
    width:100%;
    border-radius:12px;
    margin-bottom:8px;
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
for k in [
    "user_id","nome","telefone","admin",
    "admin_view","modal_item","modal_guest"
]:
    st.session_state.setdefault(k, None)

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

    tabs = st.tabs(["📦 Presentes", "👥 Convidados"])

    # =========================
    # TAB PRESENTES
    # =========================
    with tabs[0]:

        st.subheader("➕ Novo presente")

        with st.form("novo_item"):
            nome = st.text_input("Nome")
            categoria = st.text_input("Categoria")
            qtd = st.number_input("Quantidade", 0, 10, 1)
            image_url = st.text_input("URL da imagem (opcional)")
            salvar = st.form_submit_button("Salvar")

            if salvar:
                presentes_col.insert_one({
                    "nome": nome,
                    "categoria": categoria,
                    "quantidade": qtd,
                    "image_url": image_url or None
                })
                st.success("Item criado")
                st.rerun()

        st.divider()

        filtro = st.selectbox(
            "Filtro de estoque",
            ["Todos", "Somente esgotados (0)"]
        )

        for item in presentes_col.find().sort("categoria"):
            if filtro == "Somente esgotados (0)" and item["quantidade"] > 0:
                continue

            escolhidos = escolhas_col.count_documents({"presente_id": item["_id"]})

            st.markdown("<div class='card'>", unsafe_allow_html=True)

            if item.get("image_url"):
                st.image(item["image_url"], use_container_width=True)

            st.markdown(f"""
            <strong>{item['nome']}</strong><br>
            Categoria: {item['categoria']}<br>
            Quantidade: {item['quantidade']}<br>
            Escolhido: {escolhidos}x
            """, unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("👥 Ver convidados", key=f"v_{item['_id']}"):
                    st.session_state.modal_item = item["_id"]

            with c2:
                if st.button("✏️ Editar", key=f"e_{item['_id']}"):
                    with st.dialog("Editar presente"):
                        novo_nome = st.text_input("Nome", item["nome"])
                        nova_qtd = st.number_input("Quantidade", 0, 10, item["quantidade"])
                        nova_img = st.text_input("URL imagem", item.get("image_url",""))
                        if st.button("Salvar"):
                            presentes_col.update_one(
                                {"_id": item["_id"]},
                                {"$set":{
                                    "nome":novo_nome,
                                    "quantidade":nova_qtd,
                                    "image_url": nova_img or None
                                }}
                            )
                            st.rerun()

            with c3:
                if st.button("🗑️ Excluir", key=f"d_{item['_id']}"):
                    presentes_col.delete_one({"_id": item["_id"]})
                    escolhas_col.delete_many({"presente_id": item["_id"]})
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.modal_item:
            item = presentes_col.find_one({"_id": st.session_state.modal_item})
            with st.dialog(f"👥 {item['nome']}"):
                regs = list(escolhas_col.find({"presente_id": item["_id"]}))
                if not regs:
                    st.info("Nenhum convidado escolheu")
                else:
                    for r in regs:
                        st.markdown(f"**{r['nome']}**")
                        if st.button("❌ Remover escolha", key=str(r["_id"])):
                            escolhas_col.delete_one({"_id": r["_id"]})
                            presentes_col.update_one(
                                {"_id": item["_id"]},
                                {"$inc":{"quantidade":1}}
                            )
                            st.rerun()
                if st.button("Fechar"):
                    st.session_state.modal_item = None
                    st.rerun()

    # =========================
    # TAB CONVIDADOS
    # =========================
    with tabs[1]:
        for uid in escolhas_col.distinct("user_id"):
            regs = list(escolhas_col.find({"user_id": uid}))
            nome = regs[0]["nome"]
            if st.button(nome, key=uid):
                st.session_state.modal_guest = uid

        if st.session_state.modal_guest:
            regs = list(escolhas_col.find({"user_id": st.session_state.modal_guest}))
            with st.dialog(f"🎁 {regs[0]['nome']}"):
                for r in regs:
                    p = presentes_col.find_one({"_id": r["presente_id"]})
                    st.markdown(f"• {p['nome']}")
                    if st.button("❌ Remover", key=str(r["_id"])):
                        escolhas_col.delete_one({"_id": r["_id"]})
                        presentes_col.update_one(
                            {"_id": p["_id"]},
                            {"$inc":{"quantidade":1}}
                        )
                        st.rerun()
                if st.button("Fechar"):
                    st.session_state.modal_guest = None
                    st.rerun()

    st.stop()

# ======================================================
# LOGIN CONVIDADO
# ======================================================
if not st.session_state.user_id:
    st.title("🎁 Chá de Panela")
    nome = st.text_input("Nome e sobrenome")
    telefone = st.text_input("Telefone (opcional)")

    if st.button("Continuar"):
        st.session_state.nome = nome
        st.session_state.telefone = telefone
        st.session_state.user_id = gerar_user_id(nome)
        st.rerun()
    st.stop()

# ======================================================
# UX CONVIDADO
# ======================================================
tabs = st.tabs(["🎁 Escolher presentes", "📋 Meus presentes"])

# =========================
# TAB ESCOLHER
# =========================
with tabs[0]:
    busca = st.text_input("🔍 Buscar")
    categoria_filtro = st.selectbox(
        "Categoria",
        ["Todas"] + sorted(presentes_col.distinct("categoria"))
    )

    escolhas = list(escolhas_col.find({"user_id": st.session_state.user_id}))
    ids = [e["presente_id"] for e in escolhas]

    for item in presentes_col.find():
        if categoria_filtro != "Todas" and item["categoria"] != categoria_filtro:
            continue
        if busca.lower() not in item["nome"].lower():
            continue

        ja = item["_id"] in ids
        if item.get("image_url"):
            st.image(item["image_url"], use_container_width=True)

        st.markdown(f"""
        <div class="card {'ja' if ja else ''}">
        <strong>{item['nome']}</strong><br>
        {item['quantidade']} disponíveis
        </div>
        """, unsafe_allow_html=True)

        if not ja and item["quantidade"] > 0:
            if st.button("🎁 Escolher", key=f"p_{item['_id']}"):
                presentes_col.update_one(
                    {"_id": item["_id"]},
                    {"$inc":{"quantidade":-1}}
                )
                escolhas_col.insert_one({
                    "user_id": st.session_state.user_id,
                    "nome": st.session_state.nome,
                    "telefone": st.session_state.telefone,
                    "presente_id": item["_id"],
                    "data": datetime.utcnow()
                })
                st.rerun()

# =========================
# TAB MEUS PRESENTES
# =========================
with tabs[1]:
    for r in escolhas:
        p = presentes_col.find_one({"_id": r["presente_id"]})
        st.markdown(f"**{p['nome']}**")
        if st.button("❌ Remover", key=str(r["_id"])):
            escolhas_col.delete_one({"_id": r["_id"]})
            presentes_col.update_one(
                {"_id": p["_id"]},
                {"$inc":{"quantidade":1}}
            )
            st.rerun()
