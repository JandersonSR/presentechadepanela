import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import unicodedata, re, os
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
def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z0-9 ]", "", texto)
    return texto.lower().strip()

def gerar_user_id(nome):
    return f"nome_{normalizar(nome).replace(' ', '')}"

# ======================================================
# CSS — PREMIUM SAFE
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
for k in ["user_id","nome","telefone","admin"]:
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

    st.title("📊 Painel Administrativo — Chá de Panela")

    # ==================================================
    # MÉTRICAS
    # ==================================================
    total_itens = presentes_col.count_documents({})
    total_escolhas = escolhas_col.count_documents({})
    convidados = len(escolhas_col.distinct("user_id"))
    itens_sem_escolha = total_itens - len(escolhas_col.distinct("presente_id"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎁 Itens", total_itens)
    c2.metric("✅ Escolhas", total_escolhas)
    c3.metric("👥 Convidados", convidados)
    c4.metric("🟡 Sem escolha", itens_sem_escolha)

    st.divider()

    # ==================================================
    # FILTROS DE ITENS
    # ==================================================
    st.subheader("📦 Itens cadastrados")

    categorias = ["Todas"] + sorted(presentes_col.distinct("categoria"))

    f1, f2, f3 = st.columns(3)
    with f1:
        filtro_categoria = st.selectbox("Categoria", categorias)
    with f2:
        filtro_status = st.selectbox(
            "Status",
            ["Todos", "Sem escolha", "Com escolha"]
        )
    with f3:
        filtro_qtd = st.slider(
            "Quantidade disponível",
            0, 10, (0, 10)
        )

    # ==================================================
    # ITENS POR CATEGORIA (EXPANDER)
    # ==================================================
    for categoria in sorted(presentes_col.distinct("categoria")):

        if filtro_categoria != "Todas" and categoria != filtro_categoria:
            continue

        with st.expander(f"📦 {categoria}", expanded=False):

            for item in presentes_col.find({"categoria": categoria}):

                escolhidos = escolhas_col.count_documents(
                    {"presente_id": item["_id"]}
                )

                if filtro_status == "Sem escolha" and escolhidos > 0:
                    continue
                if filtro_status == "Com escolha" and escolhidos == 0:
                    continue
                if not (filtro_qtd[0] <= item["quantidade"] <= filtro_qtd[1]):
                    continue

                st.markdown(f"""
                <div class="card">
                    <strong>{item['nome']}</strong><br>
                    Restantes: {item['quantidade']}<br>
                    Escolhido: {escolhidos}x
                </div>
                """, unsafe_allow_html=True)

                # MODAL — QUEM ESCOLHEU ESSE ITEM
                if st.button("👥 Ver convidados", key=f"item_{item['_id']}"):
                    with st.dialog(f"🎁 {item['nome']}"):
                        regs = escolhas_col.find(
                            {"presente_id": item["_id"]}
                        )

                        if regs.count() == 0:
                            st.info("Nenhum convidado escolheu este item")
                        else:
                            for r in regs:
                                st.markdown(
                                    f"• **{r['nome']}** — {r.get('telefone','-')}"
                                )

    st.divider()

    # ==================================================
    # CONVIDADOS — DRILL DOWN
    # ==================================================
    st.subheader("👥 Convidados")

    convidados_lista = sorted(
        escolhas_col.distinct("user_id")
    )

    convidado_sel = st.selectbox(
        "Selecione um convidado",
        ["Selecione"] + convidados_lista
    )

    if convidado_sel != "Selecione":
        registros = list(
            escolhas_col.find({"user_id": convidado_sel})
        )

        with st.dialog("🎁 Escolhas do convidado"):
            st.markdown(f"**Convidado:** {registros[0]['nome']}")
            st.markdown(f"📞 {registros[0].get('telefone','-')}")

            st.divider()

            for r in registros:
                p = presentes_col.find_one({"_id": r["presente_id"]})
                st.markdown(f"• {p['nome']}")

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
