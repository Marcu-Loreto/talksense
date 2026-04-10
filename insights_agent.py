# insights_agent.py

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Lazy client — evita crash no import quando a env var não está definida
_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        _client = OpenAI(api_key=api_key)
    return _client


def get_insight_prompt(filename="prompt_insight_relatorio.md"):
    """Lê o prompt de insights do arquivo e utiliza cache se estiver em ambiente Streamlit."""
    prompt_path = os.path.join("prompt", filename)
    
    # Tenta usar o cache do Streamlit se disponível
    try:
        import streamlit as st
        @st.cache_data(ttl=3600)
        def _read_file(path):
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            return None
        content = _read_file(prompt_path)
        if content: return content
    except Exception:
        pass

    # Fallback ou ambiente não-Streamlit
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Você é um consultor de insights. Analise os dados fornecidos."


def gerar_insights_gestor(
    mensagens: list[str], 
    sentimentos: list[dict], 
    palavras_frequentes: list[str],
    modelo: str = "gpt-4o-mini"
) -> str:
    """
    Retorna um relatório consultivo utilizando 'prompt_insight_relatorio.md'.
    """
    if not _get_client():
        return "⚠️ A chave OPENAI_API_KEY não foi configurada corretamente."
        
    if not mensagens:
        return "Não há mensagens suficientes para gerar insights."

    # Prepara dados para o template
    textos_mensagens = "\n".join([f"- {m}" for m in mensagens[-30:]])
    scores = [s.get("score", 0.0) for s in sentimentos]
    media_sentimento_val = sum(scores) / len(scores) if scores else 0.0
    
    status_sent_str = "Neutro"
    if media_sentimento_val >= 0.3:
         status_sent_str = "Positivo"
    elif media_sentimento_val <= -0.3:
         status_sent_str = "Negativo"

    # Carrega o prompt de RELATÓRIO
    template = get_insight_prompt("prompt_insight_relatorio.md")
    
    try:
        prompt_final = template.format(
            status_sentimento=status_sent_str,
            media_sentimento=f"{media_sentimento_val:.2f}",
            palavras_frequentes=", ".join(palavras_frequentes[:15]),
            textos_mensagens=textos_mensagens
        )
    except Exception as e:
        prompt_final = f"Erro no template de prompt: {e}\n\nDados: {textos_mensagens}"

    try:
        resp = _get_client().chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Você é um consultor sênior focado em relatórios de CX."},
                {"role": "user", "content": prompt_final}
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Erro ao gerar insights: {str(e)}"

def gerar_feedback_usuario_realtime(
    mensagens: list[str],
    palavras_frequentes: list[str],
    modelo: str = "gpt-4o-mini"
) -> str:
    """
    Gera feedback direto para o usuário utilizando 'prompt_feedback_usuario.md'.
    """
    if not _get_client():
        return "⚠️ A chave OPENAI_API_KEY não foi configurada."
        
    if not mensagens:
        return ""

    textos_mensagens = "\n".join([f"- {m}" for m in mensagens[-10:]])
    
    # Carrega o prompt de FEEDBACK USUÁRIO
    template = get_insight_prompt("prompt_feedback_usuario.md")
    
    try:
        prompt_final = template.format(
            palavras_frequentes=", ".join(palavras_frequentes[:15]),
            textos_mensagens=textos_mensagens
        )
    except Exception as e:
        prompt_final = f"Erro no template: {e}\n\nÚltimas mensagens: {textos_mensagens}"

    try:
        resp = _get_client().chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Você é um Analista de IA que fornece feedback instantâneo."},
                {"role": "user", "content": prompt_final}
            ],
            temperature=0.4,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Erro na análise em tempo real: {str(e)}"