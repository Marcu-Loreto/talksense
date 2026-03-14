# dashboard_n8n.py
from datetime import datetime
import time
import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components

# qat-voxmap-atendimento-dashboard.nl9itp.easypanel.host

# Integrações locais
from shared_state import SharedState  # usa PostgreSQL > Redis > JSON
from analysis import processar_lista_mensagens  # NÃO alteramos a lógica de análise
from insights_agent import gerar_insights_gestor  # NOVO: Agente de Insights do Gestor

st.set_page_config(
    page_title="Painel de Sentimentos", layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded"
    )

st.title("📊 Painel de Sentimentos")
# st.caption("Mensagens armazenadas no banco  + análise de sentimento")
st.caption(
     f"""
            <p style="color:#ef4444; font-size:0.95rem; margin-top:0;">
            <b>Powered by Neori.Tech</b> | Versão 1.1 | {datetime.now().strftime('%Y')}
        </p>
    </div>
""",
    unsafe_allow_html=True,
)

# --- Sidebar: fonte de dados (APENAS selectbox) ---
st.sidebar.title ( "Conectado  >>>   API")
st.sidebar.caption("⚙️ Fonte de dados")

@st.cache_data(ttl=30)
def listar_sessoes(limit=500) -> list[str]:
    try:
        sessoes = SharedState.list_sessions(limit=limit) or []
        return sorted({s for s in sessoes if s})
    except Exception as e:
        st.sidebar.error(f"Erro ao listar sessões: {e}")
        return []

# dois botões lado a lado


atualizar_lista = st.sidebar.button("🔁 Atualizar lista", use_container_width=True)


# col_btn1, col_btn2 = st.sidebar.columns(2)
# with col_btn1:
#     atualizar_lista = st.button("🔁 Atualizar lista", use_container_width=True)
# with col_btn2:
#     reload_now = st.button("🔄 Recarregar dados", use_container_width=True)

if atualizar_lista:
    listar_sessoes.clear()

sessoes = listar_sessoes()
if not sessoes:
    st.sidebar.info("Nenhuma sessão encontrada no banco.")
    st.stop()

# pré-seleção pela URL (opcional)
pre = st.query_params.get("session")
idx = sessoes.index(pre) if pre in sessoes else 0

session_id = st.sidebar.selectbox("ID do Usuario", options=sessoes, index=idx, key="sessao_select")
st.query_params.update({"session": session_id})  # opcional: persistir na URL

limit = st.sidebar.number_input("Limite de mensagens", min_value=1, max_value=2000, value=200, step=10)

#auto_refresh = st.sidebar.toggle("Auto-refresh (a cada 10s)", value=False)

# from streamlit_autorefresh import st_autorefresh
# import time

# refresh_interval = 10_000 if auto_refresh else 0
# count = st_autorefresh(interval=refresh_interval, key="refresh10s")

# st.caption(f"🕒 Atualizado: {time.strftime('%H:%M:%S')}")


status_cols = st.sidebar.columns(2)
with status_cols[0]:
    st.metric("PostgreSQL", "ON" if getattr(SharedState, "DATABASE_AVAILABLE", False) else "OFF")
with status_cols[1]:
    st.metric("Redis", "ON" if getattr(SharedState, "REDIS_AVAILABLE", False) else "OFF")





@st.cache_data(ttl=5)
def carregar_mensagens(session: str, n: int) -> list[str]:
    try:
        registros = SharedState.get_messages(session, limit=n) or []
        return [m.get("content", "") for m in registros
                if (m.get("role") == "user" and m.get("content"))]
    except Exception as e:
        st.error(f"Erro ao carregar mensagens: {e}")
        return []
    
reload_now = st.sidebar.button("🔄 Recarregar dados", use_container_width=True)

if reload_now:
    carregar_mensagens.clear()

mensagens = carregar_mensagens(session_id, limit)

# evita chamada com sessão vazia
if not session_id:
    st.info("Selecione ou digite um ID de sessão na barra lateral.")
    st.stop()

mensagens = carregar_mensagens(session_id, limit)

# Auto refresh simples
# if auto_refresh:
#     # Registra um noop para invalidar cache de tempos em tempos
#     st.write(f"⏱️ Atualizando em ~10s • {time.strftime('%H:%M:%S')}")
#     st.experimental_set_query_params(ts=int(time.time()))
#     # Pequena espera para evitar loop muito agressivo ao vivo
#     time.sleep(0.2)


# if auto_refresh:
#     st.write(f"⏱️ Atualizando em ~ 10s • {time.strftime('%H:%M:%S')}")
#     st.query_params.update({"ts": str(int(time.time()))})
#     time.sleep(0.2)


if not mensagens:
    st.info("Sem mensagens para analisar. Envie mensagens via N8N/API para a sessão selecionada.")
    st.stop()

# with st.spinner("🔍 Processando mensagens..."):
#     sentimentos, grafo, wordcloud_img = processar_lista_mensagens(mensagens)

# Apenas recalcula se mensagens mudarem
if "mensagens_anteriores" not in st.session_state or st.session_state["mensagens_anteriores"] != mensagens:
    with st.spinner("🔍 Processando mensagens..."):
        sentimentos, grafo, wordcloud_img = processar_lista_mensagens(mensagens)
        st.session_state["sentimentos"] = sentimentos
        st.session_state["grafo"] = grafo
        st.session_state["wordcloud"] = wordcloud_img
        st.session_state["mensagens_anteriores"] = mensagens
else:
    sentimentos = st.session_state["sentimentos"]
    grafo = st.session_state["grafo"]
    wordcloud_img = st.session_state["wordcloud"]

    
    

# ===== UI de resultados =====
col1, col2 = st.columns(2)
with col1:
    st.subheader("📥 Mensagens (mais recentes por último)")
    for i, msg in enumerate(mensagens, start=1):
        st.markdown(f"**{i}.** {msg}")

with col2:
    st.subheader("🧠 Análise de Sentimento (por mensagem)")
    df_sent = pd.DataFrame(sentimentos)
    df_sent.index = [f"Msg {i+1}" for i in range(len(mensagens))]
    st.dataframe(df_sent, use_container_width=True)
    if "score" in df_sent.columns:
        st.line_chart(df_sent["score"], height=180, use_container_width=True)

st.divider()
st.subheader("☁️ Nuvem de Palavras")
if wordcloud_img:
    st.image(wordcloud_img, caption="Termos mais frequentes", use_container_width=True)
else:
    st.info("Sem imagem gerada.")

# ======= INSIGHTS DO GESTOR (NOVO AGENTE) ========
st.divider()
st.subheader("🤖 Insights do Gestor (Consultor AI)")
st.info("Este agente analisa o tom da conversa, os termos mais frequentes e o histórico acima para lhe dar recomendações diretas.")

if st.button("🧠 Gerar Relatório de Insights e Próximos Passos", type="primary", use_container_width=True):
    with st.spinner("O Agente Consultor está analisando a sessão..."):
        # Extrai as palavras mais frequentes diretamente do grafo para contextualizar o agente
        palavras_frequentes = []
        if grafo and isinstance(grafo, nx.Graph) and len(grafo.nodes) > 0:
            counts = nx.get_node_attributes(grafo, "count")
            palavras_ordenadas = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
            palavras_frequentes = [w for w, _ in palavras_ordenadas]

        # Chama nosso novo agente
        relatorio = gerar_insights_gestor(
            mensagens=mensagens, 
            sentimentos=sentimentos, 
            palavras_frequentes=palavras_frequentes
        )
        
        st.success("Análise concluída!")
        st.markdown(f"### 📋 Relatório Estratégico\n\n{relatorio}")

# ======= GRAFO ========

# st.divider()
# st.subheader("🔗 Grafo: Palavras Relacionadas")
# if grafo and isinstance(grafo, nx.Graph) and len(grafo.nodes) > 0:
#     net = Network(height="520px", width="100%")
#     net.barnes_hut()
#     for node, data in grafo.nodes(data=True):
#         net.add_node(node, label=node, title=f"Freq: {data.get('count', 1)}")
#     for u, v, data in grafo.edges(data=True):
#         net.add_edge(u, v, value=data.get("weight", 1))
#     net.save_graph("graph.html")
#     with open("graph.html", "r", encoding="utf-8") as f:
#         graph_html = f.read()
#     components.html(graph_html, height=540, scrolling=True)
# else:
#     st.warning("Grafo indisponível ou sem dados suficientes.")

# st.divider()
# st.subheader("🔗 Grafo: Palavras Relacionadas")

# if grafo and isinstance(grafo, nx.Graph) and len(grafo.nodes) > 0:
#     # Paleta (5 níveis): azul claro → verde → amarelo → laranja → vermelho
#     PALETA = {
#         "azul_claro": "#93C5FD",  # very low
#         "verde": "#22C55E",       # low+
#         "amarelo": "#F59E0B",     # mid
#         "laranja": "#F97316",     # high
#         "vermelho": "#EF4444",    # very high
#     }

#     counts = [grafo.nodes[n].get("count", 1) for n in grafo.nodes()]
#     vmin, vmax = (min(counts), max(counts)) if counts else (1, 1)

#     def cor_por_magnitude(valor: float) -> str:
#         if vmax == vmin:
#             return PALETA["azul_claro"]
#         t = (valor - vmin) / (vmax - vmin)
#         if t < 0.20:
#             return PALETA["azul_claro"]
#         elif t < 0.40:
#             return PALETA["verde"]
#         elif t < 0.60:
#             return PALETA["amarelo"]
#         elif t < 0.80:
#             return PALETA["laranja"]
#         else:
#             return PALETA["vermelho"]

#     net = Network(height="520px", width="100%")
#     net.barnes_hut()

#     for node, data in grafo.nodes(data=True):
#         freq = data.get("count", 1)
#         net.add_node(
#             node,
#             label=node,
#             title=f"Freq: {freq}",
#             color=cor_por_magnitude(freq),
#         )

#     for u, v, data in grafo.edges(data=True):
#         net.add_edge(u, v, value=data.get("weight", 1))

#     # Legenda
#     st.markdown(
#         f"""
#         <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:4px 0 8px 0;font-size:.9rem;">
#           <span><span style="display:inline-block;width:12px;height:12px;background:{PALETA['azul_claro']};border-radius:2px;margin-right:6px;"></span>muito baixa</span>
#           <span><span style="display:inline-block;width:12px;height:12px;background:{PALETA['verde']};border-radius:2px;margin-right:6px;"></span>baixa</span>
#           <span><span style="display:inline-block;width:12px;height:12px;background:{PALETA['amarelo']};border-radius:2px;margin-right:6px;"></span>média</span>
#           <span><span style="display:inline-block;width:12px;height:12px;background:{PALETA['laranja']};border-radius:2px;margin-right:6px;"></span>alta</span>
#           <span><span style="display:inline-block;width:12px;height:12px;background:{PALETA['vermelho']};border-radius:2px;margin-right:6px;"></span>muito alta</span>
#         </div>
#         """,
#         unsafe_allow_html=True,
#     )

#     net.save_graph("graph.html")
#     with open("graph.html", "r", encoding="utf-8") as f:
#         graph_html = f.read()
#     components.html(graph_html, height=540, scrolling=True)
# else:
#     st.warning("Grafo indisponível ou sem dados suficientes.")


# st.divider()
# st.subheader("🔗 Grafo: Palavras Relacionadas")
# #st.sidebar.write("### 🔗 Relação de Palavras")
# graph_container = st.sidebar.container()

# with graph_container:
#     min_edge_weight = st.sidebar.slider(
#         "Mín. coocorrências (aresta)",
#         1, 5, 1,
#         help="Filtra arestas fracas"
#     )
    
#     max_path_depth = st.sidebar.slider(
#         "Profundidade máx. caminho",
#         1, 8, 4,
#         help="Caminhos até a palavra alvo"
#     )
    
#     show_paths_only = st.sidebar.toggle(
#         "Mostrar apenas caminhos até palavra alvo",
#         value=True
#     )
    
#     graph_dark_mode = st.sidebar.toggle(
#         "Modo escuro (grafo)",
#         value=True
#     )

st.divider()
import base64
from itertools import combinations

# Novo título
st.subheader("🔗 Grafo de Palavras (interativo)")

# Se tiver grafo...
if grafo and isinstance(grafo, nx.Graph) and len(grafo.nodes) > 0:

    counts = nx.get_node_attributes(grafo, "count")
    palavras_ordenadas = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    palavras = [w for w, _ in palavras_ordenadas]
    palavra_alvo = st.selectbox("🔍 Palavra alvo (destaque/caminhos):", options=palavras[:100] or ["(vazio)"])

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        min_edge_weight = st.slider("Mín. coocorrência (aresta)", 1, 5, 1)
    with col_b:
        max_path_depth = st.slider("Profundidade máxima (caminho)", 1, 6, 4)
    with col_c:
        dark_mode = st.toggle("Modo escuro", value=True)

    # 🔍 Subgrafo por caminho até palavra alvo (como no app_01)
    def extrair_subgrafo(G, alvo, max_depth=4):
        if G is None or alvo not in G:
            return None
        visitados = {alvo}
        fronteira = {alvo}
        for _ in range(max_depth):
            nova_fronteira = set()
            for u in fronteira:
                for v in G.neighbors(u):
                    if v not in visitados:
                        visitados.add(v)
                        nova_fronteira.add(v)
            fronteira = nova_fronteira
        return G.subgraph(visitados).copy()

    subgrafo = extrair_subgrafo(grafo, palavra_alvo, max_depth=max_path_depth)

    if subgrafo is None or len(subgrafo.nodes) == 0:
        st.warning("Sem dados suficientes para montar o subgrafo.")
        st.stop()

    bg = "#0f172a" if dark_mode else "#ffffff"
    fg = "#e5e7eb" if dark_mode else "#333333"
    net = Network(height="580px", width="100%", bgcolor=bg, font_color=fg, notebook=False)

    net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=160, spring_strength=0.01, damping=0.9)

    node_counts = nx.get_node_attributes(subgrafo, "count")
    max_count = max(node_counts.values()) if node_counts else 1

    for node, data in subgrafo.nodes(data=True):
        count = int(data.get("count", 1))
        size = 12 + (30 * (count / max_count))
        color_high = "#34d399" if dark_mode else "#10b981"
        color_norm = "#93c5fd" if dark_mode else "#60a5fa"
        color = color_high if node == palavra_alvo else color_norm
        net.add_node(node, label=node, size=size, color=color, title=f"{node}<br/>freq: {count}")

    for u, v, data in subgrafo.edges(data=True):
        w = int(data.get("weight", 1))
        if w >= min_edge_weight:
            width = 1 + min(10, w)
            net.add_edge(u, v, value=w, width=width, title=f"{u} — {v}<br/>coocorrências: {w}")

    net.save_graph("graph.html")
    with open("graph.html", "r", encoding="utf-8") as f:
        graph_html = f.read()
    components.html(graph_html, height=600, scrolling=True)

else:
    st.warning("Grafo indisponível ou sem dados suficientes.")
