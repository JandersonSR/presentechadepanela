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

    # ================= METRICS =================
    total_itens = presentes_col.count_documents({})
    total_escolhas = escolhas_col.count_documents({})
    convidados = len(escolhas_col.distinct("user_id"))

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("🎁 Itens", total_itens)
        if st.button("📦 Gerenciar itens"):
            st.session_state.admin_view = "itens"

    with c2:
        st.metric("✅ Escolhas", total_escolhas)
        if st.button("🎁 Ver escolhas"):
            st.session_state.admin_view = "escolhas"

    with c3:
        st.metric("👥 Convidados", convidados)
        if st.button("👥 Ver convidados"):
            st.session_state.admin_view = "convidados"

    st.divider()

    # ==================================================
    # CRUD ITENS
    # ==================================================
    if st.session_state.admin_view in (None, "itens"):
        st.subheader("➕ Novo presente")

        with st.form("novo_item"):
            nome = st.text_input("Nome")
            categoria = st.text_input("Categoria")
            qtd = st.number_input("Quantidade", 1, 10, 1)
            salvar = st.form_submit_button("Salvar")

            if salvar:
                presentes_col.insert_one({
                    "nome": nome,
                    "categoria": categoria,
                    "quantidade": qtd
                })
                st.success("Item criado")
                st.rerun()

        st.divider()
        st.subheader("📦 Itens cadastrados")

        for item in presentes_col.find().sort("categoria"):
            escolhidos = escolhas_col.count_documents({"presente_id": item["_id"]})

            st.markdown(f"""
            <div class="card">
                <strong>{item['nome']}</strong><br>
                Categoria: {item['categoria']}<br>
                Quantidade: {item['quantidade']}<br>
                Escolhido: {escolhidos}x
            </div>
            """, unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("👥 Ver convidados", key=f"view_{item['_id']}"):
                    st.session_state.modal_item = item["_id"]

            with c2:
                if st.button("✏️ Editar", key=f"edit_{item['_id']}"):
                    with st.dialog("Editar item"):
                        novo_nome = st.text_input("Nome", item["nome"])
                        nova_qtd = st.number_input("Quantidade", 0, 10, item["quantidade"])
                        if st.button("Salvar"):
                            presentes_col.update_one(
                                {"_id": item["_id"]},
                                {"$set":{"nome":novo_nome,"quantidade":nova_qtd}}
                            )
                            st.rerun()

            with c3:
                if st.button("🗑️ Excluir", key=f"del_{item['_id']}"):
                    presentes_col.delete_one({"_id": item["_id"]})
                    escolhas_col.delete_many({"presente_id": item["_id"]})
                    st.rerun()

        # ================= MODAL ITEM =================
        if st.session_state.modal_item:
            item = presentes_col.find_one({"_id": st.session_state.modal_item})

            with st.dialog(f"👥 {item['nome']}"):
                regs = list(escolhas_col.find({"presente_id": item["_id"]}))

                if not regs:
                    st.info("Nenhum convidado escolheu este item")
                else:
                    for r in regs:
                        st.markdown(f"**{r['nome']}** — {r.get('telefone','-')}")
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

    # ==================================================
    # view CONVIDADOS
    # ==================================================
    if st.session_state.admin_view == "convidados":
        st.subheader("👥 Convidados")

        for uid in escolhas_col.distinct("user_id"):
            regs = list(escolhas_col.find({"user_id": uid}))
            nome = regs[0]["nome"]

            if st.button(nome, key=uid):
                st.session_state.modal_guest = uid

        if st.session_state.modal_guest:
            regs = list(escolhas_col.find({"user_id": st.session_state.modal_guest}))

            with st.dialog(f"🎁 Escolhas de {regs[0]['nome']}"):
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
# UX CONVIDADO
# ======================================================
escolhas = list(escolhas_col.find({"user_id": st.session_state.user_id}))
ids = [e["presente_id"] for e in escolhas]

st.markdown(f"### 🎁 Você escolheu **{len(ids)}** presentes")

busca = st.text_input("🔍 Buscar presente")

for categoria in sorted(presentes_col.distinct("categoria")):
    with st.expander(f"📦 {categoria}", expanded=False):

        itens = [
            i for i in presentes_col.find({"categoria": categoria})
            if busca.lower() in i["nome"].lower()
        ]

        cols = st.columns(4)

        for i, item in enumerate(itens):
            col = cols[i % 4]
            ja = item["_id"] in ids
            esgotado = item["quantidade"] <= 0

            with col:
                st.markdown(f"""
                <div class="card {'ja' if ja else ''}">
                    <strong>{item['nome']}</strong><br>
                    <small>{item['quantidade']} disponíveis</small><br>
                    {('<div class=badge>Já escolhido</div>' if ja else '')}
                </div>
                """, unsafe_allow_html=True)

                if not ja and not esgotado:
                    if st.button("🎁 Escolher", key=f"pick_{item['_id']}"):
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
                        st.success("🎉 Presente escolhido!")
                        st.rerun()

                if ja:
                    if st.button("🔄 Trocar", key=f"swap_{item['_id']}"):
                        escolhas_col.delete_one({
                            "user_id": st.session_state.user_id,
                            "presente_id": item["_id"]
                        })
                        presentes_col.update_one(
                            {"_id": item["_id"]},
                            {"$inc":{"quantidade":1}}
                        )
                        st.rerun()
