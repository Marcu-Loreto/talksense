# insights_agent.py
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None


def gerar_insights_gestor(
    mensagens: list[str], 
    sentimentos: list[dict], 
    palavras_frequentes: list[str],
    modelo: str = "gpt-4o-mini"
) -> str:
    """
    Recebe o histórico de mensagens, análises de sentimento e um resumo das palavras mais frequentes,
    e retorna um relatório consultivo voltado para a tomada de decisão gerencial.
    """
    if not client:
        return "⚠️ A chave OPENAI_API_KEY não foi configurada corretamente."
        
    if not mensagens:
        return "Não há mensagens suficientes para gerar insights."

    # Prepara um resumo rápido dos dados para o LLM
    textos_mensagens = "\n".join([f"- {m}" for m in mensagens[-30:]])  # Limita a 30 para não estourar contexto
    
    # Média de sentimento (positivo = 1, negativo = -1, neutro = 0)
    scores = [s.get("score", 0.0) for s in sentimentos]
    media_sentimento = sum(scores) / len(scores) if scores else 0.0
    
    status_sentimento = "Neutro"
    if media_sentimento >= 0.3:
         status_sentimento = "Positivo"
    elif media_sentimento <= -0.3:
         status_sentimento = "Negativo"

    prompt = f"""Você é um consultor especialista em atendimento ao cliente e experiência do usuário (UX).
Sua função é analisar os dados de uma sessão de conversa entre usuários e o sistema/agente e fornecer *insights estratégicos imediatos* para um gestor.

### Dados da Sessão:
- **Status Geral do Sentimento**: {status_sentimento} (Score médio: {media_sentimento:.2f})
- **Palavras Mais Frequentes (Temas principais)**: {', '.join(palavras_frequentes[:15])}

### Últimas mensagens do usuário:
{textos_mensagens}

### Sua Tarefa:
Com base no tom da conversa, nas principais palavras e no problema relatado, forneça um pequeno relatório estruturado em formato Markdown:
1. **Diagnóstico Breve**: O que está acontecendo nesta conversa? Qual a "dor" principal?
2. **Pontos de Atenção**: O que o gestor precisa notar imediatamente (riscos de insatisfação, gargalos, falhas no processo)?
3. **Recomendação de Ação**: Qual a melhor decisão ou próximo passo que o gestor deve tomar para resolver ou melhorar a situação relatada? Seja prático e direto.

Mantenha o tom profissional, analítico e extremamente objetivo (máximo de 3 parágrafos curtos ou bullet points).
"""

    try:
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Você é um consultor sênior de atendimento ao cliente focado em insights gerenciais acionáveis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3, # Baixa temperatura para respostas mais focadas e analíticas
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
    Gera um feedback direto em tela para o usuário após 10 segundos de inatividade,
    analisando se é uma reclamação/elogio e apontando as prováveis causas raízes
    baseadas na nuvem de palavras.
    """
    if not client:
        return "⚠️ A chave OPENAI_API_KEY não foi configurada."
        
    if not mensagens:
        return ""

    textos_mensagens = "\n".join([f"- {m}" for m in mensagens[-10:]])
    
    prompt = f"""Você é o Consultor Analítico de IA inserido no chat. Sua função é entrar na conversa quando o usuário faz uma pausa e fornecer uma análise rápida e amigável sobre o que está sendo discutido até agora.

### Dados da Conversa Atual:
- **Palavras Mais Frequentes (Nuvem de Palavras)**: {', '.join(palavras_frequentes[:15])}
- **Últimas mensagens do usuário**:
{textos_mensagens}

### Sua Tarefa:
Escreva uma mensagem de 1 a 2 pequenos parágrafos, direcionada ao usuário, informando:
1. Sua interpretação sobre o tom da conversa (se é um elogio, uma reclamação, uma dúvida, etc).
2. As possíveis "Causas Raízes" ou principais focações do problema, baseando-se explicitamente na relação das palavras encontradas na nuvem de palavras.

Seja prestativo, empático e claro. Use formatação em Markdown (negrito em palavras-chave). Comece algo como "🔍 **Análise em Tempo Real:**"
"""
    try:
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Você é um Analista de IA que fornece feedback instantâneo de intenção no chat do usuário."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Erro na análise em tempo real: {str(e)}"
