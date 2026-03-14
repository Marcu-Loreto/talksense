import os
import streamlit as st
import pandas as pd
from datetime import datetime
from insights_agent import gerar_insights_gestor

try:
    import psycopg2
    from database import Database, PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS
except Exception as e:
    Database = None
    print(f"Erro de import PostgreSQL: {e}")


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
            # Preparar o contexto de dados atuais do DataFrame para dar embasamento à IA
            mensagens_amostra = df["texto"].dropna().tail(30).tolist()
            
            # Aqui focamos apenas nas palavras (nuvem de palavras)!
            todas_palavras = " ".join(df["texto"].dropna().tolist()).lower().split()
            
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
            system_prompt = f"""Você é um Consultor Analítico de Experiência do Cliente. Sua função EXCLUSIVA é analisar a **NUVEM DE PALAVRAS** gerada das conversas entre clientes e atendentes para traçar relações diretas de Causa e Efeito gerenciais. Você NÃO interage com os clientes e não usa a análise de sentimento como base primária.

Sua tarefa é cruzar as palavras frequentes da Nuvem com as amostras de texto e SEMPRE focar nestes 3 pontos:
1. **Identificar o Problema Geral**: Qual é a principal dor baseada nas relações de palavras da nuvem?
2. **Causa e Efeito**: Como os termos mais citados estão conectados gerando este gargalo?
3. **Ações de Melhoria**: Liste ações práticas e diretas que o Gestor pode tomar para minimizar essas causas raízes.

### Dados Extraídos da Nuvem de Palavras:
- **Top Palavras Mais Frequentes**: {', '.join(palavras_frequentes_nuvem)}

### Amostra de Contexto (Últimas Mgs para entender o uso das palavras):
{textos_contexto}

Seja extremamente objetivo e use formatação clara (bullet points) focando estritamente em CAUSA E EFEITO baseado no vocabulário acima."""
            
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
# Apenas dispara relatorio automatico no painel principal se o contexto mudou
todas_mensagens_str = "".join(df["texto"].dropna().tolist()) if not df.empty else ""
if "ultimo_contexto_analisado" not in st.session_state:
    st.session_state.ultimo_contexto_analisado = ""

st.sidebar.divider()
st.sidebar.subheader("🤖 Novo Relatorio do Gestor (Consultor AI)")
st.sidebar.info("Clique abaixo ou aguarde novas mensagens para gerar o relatório atualizado.")

if st.sidebar.button("🧠 Gerar Relatório de Insights e Próximos Passos", type="primary", use_container_width=True) or (todas_mensagens_str != st.session_state.ultimo_contexto_analisado and st.session_state.ultimo_contexto_analisado != ""):
    st.session_state.ultimo_contexto_analisado = todas_mensagens_str
    
    with st.sidebar.status("Agente Consultor está analisando as novas mensagens...", expanded=True) as status:
        # Prepara contexto
        mensagens_amostra = df["texto"].dropna().tail(30).tolist()
        todas_palavras = " ".join(df["texto"].dropna().tolist()).lower().split()
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


st.sidebar.divider()

st.sidebar.header("Filtros")
sent_opts = sorted([x for x in df["sentimento"].dropna().unique()])
selecionados = st.sidebar.multiselect("Sentimentos", options=sent_opts, default=sent_opts)

min_dt = df["datahora"].min().date() if df["datahora"].notna().any() else datetime.now().date()
max_dt = df["datahora"].max().date() if df["datahora"].notna().any() else datetime.now().date()
d_ini = st.sidebar.date_input("Data inicial", min_dt)
d_fim = st.sidebar.date_input("Data final", max_dt)

mask = (
    df["sentimento"].isin(selecionados)
    & (df["datahora"].dt.date >= d_ini)
    & (df["datahora"].dt.date <= d_fim)
)
filtrado = df.loc[mask].copy()

c1, c2, c3 = st.columns(3)
c1.metric("Total", len(filtrado))
c2.metric("Positivas", (filtrado["sentimento"] == "positivo").sum())
c3.metric("Negativas", (filtrado["sentimento"] == "negativo").sum())

st.subheader("📋 Mensagens")
st.dataframe(filtrado, use_container_width=True)

st.subheader("📈 Distribuição de Sentimentos")
st.bar_chart(filtrado["sentimento"].value_counts())

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
