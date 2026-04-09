
# --- INÍCIO HACK DE COMPATIBILIDADE DE PATH ---
import sys, os
_local_path = r"C:\Users\marcu\AppData\Local\Programs\Python\Python313\Lib\site-packages"
if os.path.exists(_local_path) and _local_path not in sys.path:
    sys.path.append(_local_path)
# --- FIM HACK DE COMPATIBILIDADE DE PATH ---

import os
import streamlit as st
import pandas as pd
from datetime import datetime
from insights_agent import gerar_insights_gestor, get_insight_prompt

try:
    import psycopg2
    from database import Database, PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS
except Exception as e:
    Database = None
    print(f"Erro de import PostgreSQL: {e}")


@st.cache_data(ttl=60, show_spinner="📊 Carregando dados do banco...")
def carregar_dados():
    if not Database:
        return pd.DataFrame()

    try:
        from database import get_connection, put_connection
        conn = get_connection()
        if not conn:
            return pd.DataFrame()
            
        # Extrai os dados do PostgreSQL e também do campo metadata JSONB
        query = """
        SELECT 
            id, 
            session_id,
            COALESCE(metadata->>'user_name', 'Desconhecido') as usuario,
            created_at as datahora, 
            content as texto, 
            COALESCE(metadata->>'sentimento', 'neutro') as sentimento,
            COALESCE(metadata->>'confianca', '0') as confianca,
            COALESCE(metadata->>'emocao', 'nenhuma') as emocao,
            COALESCE(metadata->>'score', '0') as score
        FROM messages 
        WHERE role = 'user'
        ORDER BY id DESC
        """
        df = pd.read_sql_query(query, conn)
        # Tenta converter colunas numéricas
        df['confianca'] = pd.to_numeric(df['confianca'], errors='coerce').fillna(0)
        df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
    except Exception as e:
        print(f"Erro PostgreSQL: {e}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals() and conn:
            put_connection(conn)
            
    if "datahora" in df.columns:
        df["datahora"] = pd.to_datetime(df["datahora"], errors="coerce")
    return df

@st.cache_data(ttl=30, show_spinner=False)
def listar_sessoes_cached():
    if not Database:
        return []
    return Database.list_sessions(limit=100)

def baixar_csv(df):
    return df.to_csv(index=False).encode("utf-8")

st.set_page_config(page_title="Dashboard de Mensagens", layout="wide")
st.title("📊 Dashboard de Análise de Mensagens")

# ======= INSIGHTS DO GESTOR (BARRA LATERAL) ========
st.sidebar.title("🤖 Insights do Gestor")
st.sidebar.caption("Consultor AI em tempo real.")

# ===== INICIO DA LÓGICA DE REFRESH EM TEMPO REAL =====
try:
    from streamlit_autorefresh import st_autorefresh
    auto_refresh = st.sidebar.toggle("⏱️ Auto-refresh (a cada 15s)", value=True)
    if auto_refresh:
        st_autorefresh(interval=15000, key="data_refresh_insights")
        st.sidebar.caption("🔄 Atualizando automaticamente...")
except ImportError:
    st.sidebar.warning("⚠️ Instale 'streamlit-autorefresh' (`pip install streamlit-autorefresh`) para leitura em tempo real contínua.")
# ===== FIM DA LÓGICA DE REFRESH =====

df = carregar_dados()
if df.empty:
    st.warning("Nenhuma mensagem encontrada no banco de dados.")
    st.stop()

# ======= FILTROS E SELEÇÃO DE SESSÃO =======
st.sidebar.divider()
st.sidebar.header("🎯 Filtros e Sessão")

# Monta mapeamento de session_id → nome do usuário (mais intuitivo)
_sessoes_usuarios = (
    df.groupby("session_id")["usuario"]
    .first()
    .reset_index()
)
# Cria label legível: "Nome (session_id)" — ou só o nome se for único
_contagem_nomes = _sessoes_usuarios["usuario"].value_counts()
_opcoes_mapa = {}  # label → session_id
for _, row in _sessoes_usuarios.iterrows():
    nome = row["usuario"]
    sid = row["session_id"]
    if _contagem_nomes.get(nome, 0) > 1:
        label = f"{nome} ({sid[:12]}…)" if len(sid) > 12 else f"{nome} ({sid})"
    else:
        label = nome
    _opcoes_mapa[label] = sid

_opcoes_labels = sorted(_opcoes_mapa.keys())

sessao_label = st.sidebar.selectbox(
    "Selecionar Conversa (por usuário)",
    options=["Todas as Conversas"] + _opcoes_labels,
    help="Escolha um usuário/conversa para analisar ou veja o consolidado."
)

# Converte label selecionado de volta para session_id
sessao_selecionada = (
    _opcoes_mapa[sessao_label] if sessao_label != "Todas as Conversas" else "Todas as Conversas"
)

# Filtro de Período
min_dt = df["datahora"].min().date() if df["datahora"].notna().any() else datetime.now().date()
max_dt = df["datahora"].max().date() if df["datahora"].notna().any() else datetime.now().date()
d_ini = st.sidebar.date_input("Data inicial", min_dt)
d_fim = st.sidebar.date_input("Data final", max_dt)

# Aplicação da Máscara de Filtros (usuário + janela de tempo)
mask = (
    (df["datahora"].dt.date >= d_ini)
    & (df["datahora"].dt.date <= d_fim)
)

if sessao_selecionada != "Todas as Conversas":
    mask = mask & (df["session_id"] == sessao_selecionada)

filtrado = df.loc[mask].copy()

# Botões de Ação
col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("🗑️ Limpar Chat", use_container_width=True):
    st.session_state.insights_chat = []
    st.session_state.ultimo_contexto_analisado = ""
    st.rerun()

if col_btn2.button("🔄 Cache", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Botão para reprocessar sentimentos de mensagens antigas
if st.sidebar.button("🧠 Reprocessar Sentimentos", use_container_width=True, help="Analisa sentimento de mensagens antigas que ainda não foram classificadas"):
    try:
        from analysis import analisar_sentimento as _analisar, score_from_label as _score
        pendentes = Database.get_messages_without_sentiment(limit=200) if Database else []
        if not pendentes:
            st.sidebar.success("✅ Todas as mensagens já possuem sentimento.")
        else:
            barra = st.sidebar.progress(0, text=f"Processando 0/{len(pendentes)}...")
            processadas = 0
            for i, msg in enumerate(pendentes):
                try:
                    res = _analisar(msg["content"])
                    label = res.get("label", "neutro")
                    conf = float(res.get("confidence", 0.0))
                    emotions = res.get("emotions", [])
                    score = _score(label, conf)
                    Database.update_metadata(msg["id"], {
                        "sentimento": label,
                        "confianca": str(conf),
                        "emocao": emotions[0] if emotions else "nenhuma",
                        "score": str(score),
                    })
                    processadas += 1
                except Exception:
                    pass
                barra.progress((i + 1) / len(pendentes), text=f"Processando {i+1}/{len(pendentes)}...")
            st.sidebar.success(f"✅ {processadas}/{len(pendentes)} mensagens reprocessadas.")
            st.cache_data.clear()
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro: {e}")

st.sidebar.divider()

# Inicializa o histórico de chat da barra lateral na sessão
if "insights_chat" not in st.session_state:
    st.session_state.insights_chat = []
    
    # Ao iniciar, recupera os últimos do PostgreSQL
    if Database:
        historico_db = Database.get_latest_insights(limit=5)
        # O histórico vem do mais novo para o mais velho (DESC)
        for h in reversed(historico_db):
            st.session_state.insights_chat.append({"role": "assistant", "content": h["insight_text"]})

# Exibe as mensagens do histórico na barra lateral
for msg in st.session_state.insights_chat:
    with st.sidebar.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Caixa de input para o gestor conversar com a IA na barra lateral
if prompt := st.sidebar.chat_input("Pergunte algo ao consultor..."):
    # Salva e exibe a pergunta do gestor
    st.session_state.insights_chat.append({"role": "user", "content": prompt})
    with st.sidebar.chat_message("user"):
        st.markdown(prompt)
        
    with st.sidebar.chat_message("assistant"):
        with st.spinner("Analisando..."):
            # Preparar o contexto de dados do 'filtrado' (respeitando a sessão selecionada)
            mensagens_amostra = filtrado["texto"].dropna().tail(30).tolist()
            
            # Aqui focamos apenas nas palavras (nuvem de palavras)!
            todas_palavras = " ".join(filtrado["texto"].dropna().tolist()).lower().split()
            
            # Filtro básico (removendo palavras muito curtas)
            palavras_filtro = [p for p in todas_palavras if len(p) > 4]
            from collections import Counter
            palavras_frequentes_nuvem = [word for word, count in Counter(palavras_filtro).most_common(25)]
            
            # Chama a API da OpenAI direto aqui na sidebar focando na nuvem de palavras
            import os
            import json
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Monta o contexto para o LLM responder focando na NUVEM DE PALAVRAS e CAUSA/EFEITO
            textos_contexto = "\n".join([f"- {m}" for m in mensagens_amostra])
            # Carrega o prompt especializado para CHAT (cacheado)
            template = get_insight_prompt("prompt_insight_chat.md")
            
            # Preenche o template para o chat interativo
            try:
                system_prompt = template.format(
                    status_sentimento="(Analise baseada na Nuvem)",
                    media_sentimento="N/A",
                    palavras_frequentes=", ".join(palavras_frequentes_nuvem),
                    textos_mensagens=textos_contexto
                )
            except Exception as e:
                system_prompt = f"Erro no template de prompt: {e}"
            
            # Histórico do chat (mandamos as últimas mensagens do chat da sidebar tbm)
            messages_llm = [{"role": "system", "content": system_prompt}]
            for m in st.session_state.insights_chat[-5:]:
                messages_llm.append({"role": m["role"], "content": m["content"]})
            
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_llm,
                    temperature=0.3,
                    max_tokens=600
                )
                resposta = resp.choices[0].message.content.strip()
                
                # Salva no PostgreSQL
                if Database:
                    Database.add_insight(", ".join(palavras_frequentes_nuvem), resposta)
            except Exception as e:
                resposta = f"❌ Erro ao consultar a API: {e}"
                
            st.markdown(resposta)
            st.session_state.insights_chat.append({"role": "assistant", "content": resposta})

# ====== ANÁLISE PRÓ-ATIVA EM TEMPO REAL ======
# Apenas dispara relatorio automatico no painel principal se o contexto (filtrado) mudou
todas_mensagens_str = "".join(filtrado["texto"].dropna().tolist()) if not filtrado.empty else ""
if "ultimo_contexto_analisado" not in st.session_state:
    st.session_state.ultimo_contexto_analisado = ""

st.sidebar.divider()
st.sidebar.subheader("🤖 Novo Relatorio do Gestor")
st.sidebar.info("Clique abaixo para gerar o relatório da seleção atual.")

if st.sidebar.button("🧠 Gerar Relatório de Insights", type="primary", use_container_width=True) or (todas_mensagens_str != st.session_state.ultimo_contexto_analisado and st.session_state.ultimo_contexto_analisado != ""):
    st.session_state.ultimo_contexto_analisado = todas_mensagens_str
    
    with st.sidebar.status("Analisando mensagens selecionadas...", expanded=True) as status:
        # Prepara contexto base do filtrado
        mensagens_amostra = filtrado["texto"].dropna().tail(30).tolist()
        todas_palavras = " ".join(filtrado["texto"].dropna().tolist()).lower().split()
        palavras_filtro = [p for p in todas_palavras if len(p) > 4]
        from collections import Counter
        palavras_frequentes_nuvem = [word for word, count in Counter(palavras_filtro).most_common(25)]
        
        # Chama nosso novo agente exportado via import (do insights_agent.py)
        # O gerar_insights_gestor vai retornar a string formatada
        try:
            relatorio = gerar_insights_gestor(
                mensagens=mensagens_amostra, 
                sentimentos=[], # O agente agora foca nas palavras
                palavras_frequentes=palavras_frequentes_nuvem
            )
            # Salva no PostgreSQL
            if Database:
                Database.add_insight(", ".join(palavras_frequentes_nuvem), relatorio)
                
            st.session_state.insights_chat.append({"role": "assistant", "content": f"**⚡ ANÁLISE AUTOMÁTICA EM TEMPO REAL ⚡**\n\n{relatorio}"})
            st.rerun() # Atualiza a tela imediatamente para desenhar a mensagem na sidebar
        except Exception as e:
            st.error(f"Erro ao gerar análise: {e}")
            status.update(label="Erro!", state="error")



c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", len(filtrado))
c2.metric("Positivas", (filtrado["sentimento"] == "positivo").sum())
c3.metric("Negativas", (filtrado["sentimento"] == "negativo").sum())
c4.metric("Neutras", (filtrado["sentimento"] == "neutro").sum())

# ======= NUVEM DE PALAVRAS + DISTRIBUIÇÃO DE SENTIMENTO =======
col_wc, col_sent = st.columns(2)

with col_wc:
    st.subheader("☁️ Nuvem de Palavras")
    if not filtrado.empty:
        try:
            from analysis import tokenize_pt, gerar_wordcloud
            todos_tokens = []
            for texto in filtrado["texto"].dropna():
                todos_tokens.extend(tokenize_pt(texto))
            if todos_tokens:
                corpus = " ".join(todos_tokens)
                wc_img = gerar_wordcloud(corpus)
                st.image(wc_img, use_container_width=True)
            else:
                st.info("Sem palavras suficientes para gerar a nuvem.")
        except Exception as e:
            st.warning(f"Erro ao gerar nuvem de palavras: {e}")
    else:
        st.info("Sem dados para o filtro selecionado.")

with col_sent:
    st.subheader("📊 Distribuição de Sentimento")
    if not filtrado.empty:
        # Conta apenas mensagens que têm sentimento real (não o default)
        sent_counts = filtrado["sentimento"].value_counts()
        if len(sent_counts) > 0:
            cores = {"positivo": "#2ecc71", "neutro": "#95a5a6", "negativo": "#e74c3c"}
            chart_colors = [cores.get(s, "#3498db") for s in sent_counts.index]
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.bar(sent_counts.index, sent_counts.values, color=chart_colors)
            ax.set_ylabel("Quantidade")
            ax.set_xlabel("")
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Nenhum sentimento classificado ainda.")
    else:
        st.info("Sem dados para o filtro selecionado.")

# ======= TABELA DE MENSAGENS =======
st.subheader("📋 Mensagens")
st.dataframe(filtrado, use_container_width=True)

# ======= EVOLUÇÃO DO SENTIMENTO NO TEMPO =======
st.subheader("📈 Evolução do Sentimento no Tempo")
if not filtrado.empty:
    chart_df = filtrado.sort_values("datahora")[["datahora", "score", "sentimento"]].copy()
    if chart_df["score"].abs().sum() > 0:
        import matplotlib.pyplot as plt
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        cores_linha = {"positivo": "#2ecc71", "neutro": "#95a5a6", "negativo": "#e74c3c"}
        for _, row in chart_df.iterrows():
            cor = cores_linha.get(row["sentimento"], "#3498db")
            ax2.scatter(row["datahora"], row["score"], color=cor, s=40, zorder=3)
        ax2.plot(chart_df["datahora"], chart_df["score"], color="#bdc3c7", linewidth=1, zorder=1)
        ax2.axhline(y=0, color="#7f8c8d", linestyle="--", linewidth=0.8)
        ax2.set_ylabel("Score")
        ax2.set_xlabel("")
        ax2.set_ylim(-1.1, 1.1)
        # Legenda
        from matplotlib.lines import Line2D
        legend_items = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#2ecc71', markersize=8, label='Positivo'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#95a5a6', markersize=8, label='Neutro'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#e74c3c', markersize=8, label='Negativo'),
        ]
        ax2.legend(handles=legend_items, loc='upper right', fontsize=8)
        plt.tight_layout()
        st.pyplot(fig2)
        plt.close(fig2)
    else:
        st.info("Os sentimentos ainda não foram classificados. Clique em '🧠 Reprocessar Sentimentos' na barra lateral.")
else:
    st.info("Sem dados suficientes para gerar o gráfico.")

csv = baixar_csv(filtrado)
st.download_button("📥 Baixar CSV", csv, "mensagens_filtradas.csv", "text/csv")


# import streamlit as st
# import sqlite3
# import pandas as pd
# from datetime import datetime

# # Caminho do banco
# DB_PATH = "db.py"

# def carregar_dados():
#     conn = sqlite3.connect(DB_PATH)
#     df = pd.read_sql_query("SELECT * FROM mensagens ORDER BY id DESC", conn)
#     conn.close()
#     return df

# def baixar_csv(df):
#     return df.to_csv(index=False).encode("utf-8")

# st.set_page_config(page_title="Dashboard de Mensagens", layout="wide")
# st.title("📊 Dashboard de Análise de Mensagens")

# # Carrega dados
# df = carregar_dados()

# if df.empty:
#     st.warning("Nenhuma mensagem encontrada no banco de dados.")
#     st.stop()

# # Filtros
# st.sidebar.header("Filtros")
# sentimentos = st.sidebar.multiselect("Filtrar por Sentimento", options=df["sentimento"].unique(), default=list(df["sentimento"].unique()))
# data_inicio = st.sidebar.date_input("Data inicial", df["datahora"].min())
# data_fim = st.sidebar.date_input("Data final", df["datahora"].max())

# # Aplica filtros
# mask = (
#     df["sentimento"].isin(sentimentos) &
#     (pd.to_datetime(df["datahora"]).dt.date >= data_inicio) &
#     (pd.to_datetime(df["datahora"]).dt.date <= data_fim)
# )
# filtrado = df.loc[mask]

# # Métricas
# col1, col2, col3 = st.columns(3)
# col1.metric("Total de Mensagens", len(filtrado))
# col2.metric("Positivas", (filtrado["sentimento"] == "positivo").sum())
# col3.metric("Negativas", (filtrado["sentimento"] == "negativo").sum())

# # Tabela
# st.subheader("📋 Mensagens Filtradas")
# st.dataframe(filtrado, use_container_width=True)

# # Gráfico
# st.subheader("📈 Distribuição de Sentimentos")
# st.bar_chart(filtrado["sentimento"].value_counts())

# # Exportar CSV
# csv = baixar_csv(filtrado)
# st.download_button("📥 Baixar CSV", csv, "mensagens_filtradas.csv", "text/csv")