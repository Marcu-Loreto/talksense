"""
Teste funcional: Simula 100 interações de conversa entre um usuário fictício
e o agente de atendimento, verificando se a nuvem de palavras e o grafo de
palavras estão sincronizados (usam os mesmos tokens).

Também valida que o sentimento é gerado para cada mensagem.
"""

import json
from unittest.mock import patch, MagicMock
from collections import Counter

import pytest

# ═══════════════════════════════════════════════════════════════
# DADOS: 100 mensagens simuladas de conversa
# ═══════════════════════════════════════════════════════════════

CONVERSA_SIMULADA = [
    # Saudações e início
    ("user", "Olá, bom dia! Meu nome é Carlos Silva"),
    ("assistant", "Bom dia Carlos! Como posso ajudá-lo hoje?"),
    ("user", "Preciso de ajuda com meu pedido número 45678"),
    ("assistant", "Claro! Vou verificar o pedido 45678 para você."),
    ("user", "O pedido está atrasado já faz uma semana"),
    ("assistant", "Entendo sua preocupação. Vou verificar o status da entrega."),
    ("user", "Estou muito insatisfeito com esse atraso"),
    ("assistant", "Peço desculpas pelo transtorno. Vou priorizar a resolução."),
    ("user", "Já é a terceira vez que isso acontece"),
    ("assistant", "Lamento muito. Vou escalar para o setor responsável."),
    # Problemas com produto
    ("user", "Além do atraso o último produto veio com defeito"),
    ("assistant", "Sinto muito por isso. Poderia descrever o defeito?"),
    ("user", "A tela do notebook veio com um risco grande"),
    ("assistant", "Vamos providenciar a troca imediatamente."),
    ("user", "Quero saber como funciona a política de troca"),
    ("assistant", "Nossa política permite troca em até 30 dias após o recebimento."),
    ("user", "E o frete da devolução quem paga"),
    ("assistant", "O frete de devolução é por nossa conta quando há defeito."),
    ("user", "Preciso de um comprovante para a empresa"),
    ("assistant", "Vou gerar um protocolo de atendimento para você."),
    ("user", "O protocolo pode ser enviado por email"),
    ("assistant", "Sim! Qual email você gostaria de receber?"),
    # Dados pessoais
    ("user", "Meu email é carlos.silva@empresa.com"),
    ("assistant", "Anotado! Enviarei o protocolo para esse email."),
    ("user", "Também preciso do número do protocolo agora"),
    ("assistant", "Seu protocolo é ATD-2025-78901. Anote por favor."),
    ("user", "Obrigado pelo protocolo vou anotar"),
    ("assistant", "Por nada! Posso ajudar com mais alguma coisa?"),
    # Novo problema
    ("user", "Sim tenho outro problema com a garantia"),
    ("assistant", "Claro, me conte sobre o problema com a garantia."),
    ("user", "Comprei um monitor há seis meses e parou de funcionar"),
    ("assistant", "O monitor ainda está dentro da garantia de 12 meses."),
    ("user", "Como faço para acionar a garantia"),
    ("assistant", "Você precisa enviar a nota fiscal e fotos do defeito."),
    ("user", "Posso enviar as fotos por aqui mesmo"),
    ("assistant", "Sim, pode enviar as fotos por este chat."),
    ("user", "Vou tirar as fotos agora e já envio"),
    ("assistant", "Perfeito! Aguardo as fotos para dar andamento."),
    ("user", "Pronto enviei as fotos do monitor com defeito"),
    ("assistant", "Recebi as fotos. Vou abrir o chamado de garantia."),
    ("user", "Quanto tempo demora o processo de garantia"),
    ("assistant", "O prazo é de 5 a 10 dias úteis para análise."),
    # Reclamações
    ("user", "Dez dias é muito tempo preciso do monitor para trabalhar"),
    ("assistant", "Entendo a urgência. Vou solicitar prioridade no seu caso."),
    ("user", "Minha produtividade está sendo prejudicada"),
    ("assistant", "Vou verificar se temos um monitor disponível para empréstimo."),
    ("user", "Isso seria ótimo um empréstimo resolveria meu problema"),
    ("assistant", "Temos um modelo similar disponível. Posso enviar amanhã."),
    ("user", "Perfeito por favor envie o mais rápido possível"),
    ("assistant", "Vou agendar a entrega para amanhã pela manhã."),
    # Elogios parciais
    ("user", "Agradeço muito pela solução rápida"),
    ("assistant", "Fico feliz em poder ajudar! Algo mais?"),
    ("user", "O atendimento de hoje está sendo muito bom"),
    ("assistant", "Obrigado pelo feedback positivo Carlos!"),
    ("user", "Diferente das outras vezes que fui mal atendido"),
    ("assistant", "Lamento pelas experiências anteriores. Estamos melhorando."),
    # Dúvidas sobre pagamento
    ("user", "Tenho uma dúvida sobre o pagamento da fatura"),
    ("assistant", "Claro! Qual sua dúvida sobre a fatura?"),
    ("user", "A fatura veio com um valor diferente do combinado"),
    ("assistant", "Vou verificar os valores. Qual o número da fatura?"),
    ("user", "A fatura é número FAT-2025-3456"),
    ("assistant", "Encontrei a fatura. O valor correto é R$ 2.450,00."),
    ("user", "Na fatura está cobrando R$ 2.890 que é errado"),
    ("assistant", "Identificamos a diferença. Vou solicitar a correção."),
    ("user", "Preciso da fatura corrigida até sexta-feira"),
    ("assistant", "A fatura corrigida será enviada até quinta-feira."),
    ("user", "Posso pagar com boleto ou só cartão"),
    ("assistant", "Aceitamos boleto, cartão e PIX."),
    ("user", "Vou pagar com PIX assim que receber a fatura corrigida"),
    ("assistant", "Perfeito! Enviaremos a chave PIX junto com a fatura."),
    # Problemas técnicos
    ("user", "Outra coisa o software que comprei não está funcionando"),
    ("assistant", "Qual software e qual o erro que aparece?"),
    ("user", "O software de gestão mostra erro de licença inválida"),
    ("assistant", "Vou verificar sua licença no sistema."),
    ("user", "Já tentei reinstalar mas o erro persiste"),
    ("assistant", "Sua licença expirou ontem. Vou renovar agora."),
    ("user", "A licença não deveria ter expirado paguei por um ano"),
    ("assistant", "Tem razão, houve um erro no sistema. Já renovei por mais 12 meses."),
    ("user", "Obrigado por resolver rápido"),
    ("assistant", "Disponha! A nova licença já está ativa."),
    # Sugestões
    ("user", "Vocês deveriam melhorar o sistema de acompanhamento de pedidos"),
    ("assistant", "Agradeço a sugestão! Vou encaminhar para a equipe de produto."),
    ("user", "Seria bom ter um aplicativo para acompanhar entregas"),
    ("assistant", "Estamos desenvolvendo um app que será lançado em breve."),
    ("user", "Quando o aplicativo vai ficar pronto"),
    ("assistant", "A previsão é para o próximo trimestre."),
    ("user", "Espero que funcione melhor que o site atual"),
    ("assistant", "Estamos investindo bastante em qualidade e usabilidade."),
    # Finalização
    ("user", "Vou resumir tudo que preciso resolver"),
    ("assistant", "Claro, pode listar os pontos pendentes."),
    ("user", "Primeiro a troca do notebook com defeito"),
    ("assistant", "Já está em andamento, protocolo ATD-2025-78901."),
    ("user", "Segundo o empréstimo do monitor"),
    ("assistant", "Agendado para entrega amanhã pela manhã."),
    ("user", "Terceiro a correção da fatura"),
    ("assistant", "Será enviada até quinta-feira por email."),
    ("user", "Quarto a garantia do monitor com defeito"),
    ("assistant", "Chamado aberto, prazo de 5 a 10 dias úteis."),
    ("user", "Quinto a renovação da licença do software"),
    ("assistant", "Já renovada por mais 12 meses."),
    ("user", "Acho que é tudo por agora"),
    ("assistant", "Perfeito Carlos! Todos os pontos estão registrados."),
    ("user", "Se precisar entro em contato novamente"),
    ("assistant", "Estaremos à disposição! Tenha um ótimo dia."),
    ("user", "Obrigado pelo excelente atendimento de hoje"),
    ("assistant", "Obrigado Carlos! Foi um prazer atendê-lo."),
]

# Garante pelo menos 100 interações
assert len(CONVERSA_SIMULADA) >= 100, f"Conversa tem {len(CONVERSA_SIMULADA)} interações, precisa de 100+"


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _fake_sentiment(label="positivo", confidence=0.8):
    content = json.dumps({
        "label": label, "confidence": confidence,
        "emotions": ["teste"], "reason": "simulação"
    })
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _get_user_messages():
    return [msg for role, msg in CONVERSA_SIMULADA if role == "user"]


# ═══════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════

class TestWordCloudGraphSync:
    """
    Verifica que a nuvem de palavras e o grafo usam exatamente
    os mesmos tokens — ou seja, estão sincronizados.
    """

    def _simulate_full_conversation(self):
        """
        Simula o pipeline completo do app.py:
        1. Tokeniza cada mensagem do usuário
        2. Acumula corpus (para nuvem) e token_sequences (para grafo)
        3. Retorna ambos para comparação
        """
        from analysis import tokenize_pt

        user_corpus_text = ""
        user_token_sequences = []

        for role, content in CONVERSA_SIMULADA:
            if role != "user":
                continue
            tokens = tokenize_pt(content)
            if tokens:
                user_corpus_text += " " + " ".join(tokens)
                user_token_sequences.append(tokens)

        return user_corpus_text.strip(), user_token_sequences

    def test_conversa_tem_100_interacoes(self):
        assert len(CONVERSA_SIMULADA) >= 100

    def test_50_mensagens_do_usuario(self):
        user_msgs = _get_user_messages()
        assert len(user_msgs) == 53

    def test_tokens_corpus_e_sequences_sincronizados(self):
        """
        O corpus (string) e as sequences (lista de listas) devem
        conter exatamente os mesmos tokens na mesma quantidade.
        """
        corpus_text, token_sequences = self._simulate_full_conversation()

        # Tokens do corpus (usado pela nuvem de palavras)
        corpus_tokens = corpus_text.split()
        corpus_counter = Counter(corpus_tokens)

        # Tokens das sequences (usado pelo grafo)
        seq_tokens = []
        for seq in token_sequences:
            seq_tokens.extend(seq)
        seq_counter = Counter(seq_tokens)

        # Devem ser idênticos
        assert corpus_counter == seq_counter, (
            f"Dessincronização! "
            f"Corpus tem {len(corpus_tokens)} tokens, "
            f"Sequences tem {len(seq_tokens)} tokens. "
            f"Diferença: {set(corpus_counter.keys()) ^ set(seq_counter.keys())}"
        )

    def test_nuvem_de_palavras_gera_imagem(self):
        """Verifica que a nuvem de palavras é gerada com sucesso."""
        from analysis import gerar_wordcloud

        corpus_text, _ = self._simulate_full_conversation()
        assert len(corpus_text) > 0

        img_buf = gerar_wordcloud(corpus_text)
        assert img_buf is not None
        assert img_buf.getbuffer().nbytes > 0

    def test_grafo_gera_nos_e_arestas(self):
        """Verifica que o grafo é construído com nós e arestas."""
        from analysis import build_word_graph

        _, token_sequences = self._simulate_full_conversation()
        assert len(token_sequences) > 0

        G = build_word_graph(token_sequences)
        assert G is not None
        assert len(G.nodes()) > 0
        assert len(G.edges()) > 0

    def test_palavras_top_nuvem_presentes_no_grafo(self):
        """
        As palavras mais frequentes da nuvem DEVEM existir como
        nós no grafo — se não existem, estão dessincronizados.
        """
        from analysis import build_word_graph

        corpus_text, token_sequences = self._simulate_full_conversation()

        # Top 20 palavras da nuvem
        corpus_tokens = corpus_text.split()
        top_20_nuvem = [w for w, _ in Counter(corpus_tokens).most_common(20)]

        # Nós do grafo
        G = build_word_graph(token_sequences)
        graph_nodes = set(G.nodes())

        # Todas as top 20 da nuvem devem estar no grafo
        missing = [w for w in top_20_nuvem if w not in graph_nodes]
        assert len(missing) == 0, (
            f"Palavras da nuvem ausentes no grafo: {missing}"
        )

    def test_grafo_nos_tem_contagem_correta(self):
        """Verifica que a contagem de cada nó no grafo bate com a frequência real."""
        from analysis import build_word_graph

        _, token_sequences = self._simulate_full_conversation()

        # Contagem real
        all_tokens = []
        for seq in token_sequences:
            all_tokens.extend(seq)
        real_counts = Counter(all_tokens)

        # Contagem no grafo
        G = build_word_graph(token_sequences)
        for node, data in G.nodes(data=True):
            graph_count = data.get("count", 0)
            assert graph_count == real_counts[node], (
                f"Nó '{node}': grafo={graph_count}, real={real_counts[node]}"
            )

    def test_grafo_arestas_coocorrencia_valida(self):
        """Verifica que as arestas do grafo representam coocorrências reais."""
        from analysis import build_word_graph

        _, token_sequences = self._simulate_full_conversation()
        G = build_word_graph(token_sequences)

        # Cada aresta deve ter peso >= 1
        for u, v, data in G.edges(data=True):
            weight = data.get("weight", 0)
            assert weight >= 1, f"Aresta {u}-{v} com peso {weight} < 1"

    def test_processar_lista_mensagens_retorna_tudo(self):
        """
        Testa a função processar_lista_mensagens do analysis.py
        que é usada pelo dashboard_n8n.py — deve retornar sentimentos,
        grafo e nuvem sincronizados.
        """
        from analysis import processar_lista_mensagens

        user_msgs = _get_user_messages()

        with patch("analysis.client") as mock_client:
            # Mock para todas as chamadas de sentimento
            mock_client.chat.completions.create.return_value = _fake_sentiment()

            sentimentos, grafo, wordcloud_img = processar_lista_mensagens(user_msgs)

        # Deve ter 1 sentimento por mensagem
        assert len(sentimentos) == len(user_msgs)

        # Grafo deve ter nós
        assert grafo is not None
        assert len(grafo.nodes()) > 0

        # Nuvem deve ter imagem
        assert wordcloud_img is not None

    def test_processar_lista_nuvem_e_grafo_mesmos_tokens(self):
        """
        Verifica que processar_lista_mensagens gera grafo e nuvem
        a partir dos mesmos tokens.
        """
        from analysis import processar_lista_mensagens, tokenize_pt

        user_msgs = _get_user_messages()

        with patch("analysis.client") as mock_client:
            mock_client.chat.completions.create.return_value = _fake_sentiment()
            sentimentos, grafo, wordcloud_img = processar_lista_mensagens(user_msgs)

        # Reconstrói os tokens esperados
        expected_tokens = []
        for msg in user_msgs:
            expected_tokens.extend(tokenize_pt(msg))
        expected_counter = Counter(expected_tokens)

        # Verifica que o grafo tem os mesmos tokens
        graph_counts = dict(grafo.nodes(data="count"))
        for word, count in expected_counter.items():
            assert word in graph_counts, f"'{word}' ausente no grafo"
            assert graph_counts[word] == count, (
                f"'{word}': esperado={count}, grafo={graph_counts[word]}"
            )


class TestSentimentPerMessage:
    """Verifica que cada mensagem do usuário recebe análise de sentimento."""

    @patch("analysis.client")
    def test_todas_mensagens_tem_sentimento(self, mock_client):
        from analysis import analisar_sentimento

        user_msgs = _get_user_messages()
        sentiments = []

        for i, msg in enumerate(user_msgs):
            # Alterna sentimentos para simular conversa real
            if i % 3 == 0:
                mock_client.chat.completions.create.return_value = _fake_sentiment("negativo", 0.8)
            elif i % 3 == 1:
                mock_client.chat.completions.create.return_value = _fake_sentiment("neutro", 0.6)
            else:
                mock_client.chat.completions.create.return_value = _fake_sentiment("positivo", 0.9)

            result = analisar_sentimento(msg)
            sentiments.append(result)

        # Todas devem ter label válido
        assert len(sentiments) == 53
        for s in sentiments:
            assert s["label"] in {"positivo", "neutro", "negativo"}
            assert 0.0 <= s["confidence"] <= 1.0

    @patch("analysis.client")
    def test_metadata_completo_para_cada_mensagem(self, mock_client):
        """Simula a construção do metadata para cada mensagem."""
        from analysis import analisar_sentimento, score_from_label

        user_msgs = _get_user_messages()
        mock_client.chat.completions.create.return_value = _fake_sentiment("positivo", 0.85)

        for msg in user_msgs:
            resultado = analisar_sentimento(msg)
            label = resultado["label"]
            confidence = resultado["confidence"]
            score = score_from_label(label, confidence)
            emotions = resultado.get("emotions", [])

            metadata = {
                "sentimento": label,
                "confianca": str(confidence),
                "emocao": emotions[0] if emotions else "nenhuma",
                "score": str(score),
            }

            # Todos os campos devem ser strings
            assert all(isinstance(v, str) for v in metadata.values())
            # Nenhum campo vazio
            assert all(len(v) > 0 for v in metadata.values())


class TestAppGraphBuildFunction:
    """Testa a função build_word_graph do app.py com dados da simulação."""

    def test_build_graph_app_version(self):
        """Testa a versão do app.py que tem sliding window."""
        from app import build_word_graph
        from analysis import tokenize_pt

        user_msgs = _get_user_messages()
        token_sequences = [tokenize_pt(msg) for msg in user_msgs if tokenize_pt(msg)]

        G = build_word_graph(token_sequences, min_edge_weight=1, max_nodes=500, window_size=3)

        assert G is not None
        assert len(G.nodes()) > 0
        assert len(G.edges()) > 0

    def test_app_graph_has_same_nodes_as_analysis(self):
        """
        O grafo do app.py (sliding window) e o do analysis.py (adjacência)
        devem ter os mesmos NÓS (palavras), mesmo que as arestas difiram.
        """
        from app import build_word_graph as app_build
        from analysis import build_word_graph as analysis_build, tokenize_pt

        user_msgs = _get_user_messages()
        token_sequences = [tokenize_pt(msg) for msg in user_msgs if tokenize_pt(msg)]

        G_app = app_build(token_sequences, min_edge_weight=1, max_nodes=500)
        G_analysis = analysis_build(token_sequences, min_edge_weight=1)

        app_nodes = set(G_app.nodes())
        analysis_nodes = set(G_analysis.nodes())

        # Os nós devem ser idênticos
        assert app_nodes == analysis_nodes, (
            f"Nós diferentes! "
            f"Só no app: {app_nodes - analysis_nodes}, "
            f"Só no analysis: {analysis_nodes - app_nodes}"
        )

    def test_app_graph_node_counts_match(self):
        """As contagens dos nós devem ser iguais em ambas versões."""
        from app import build_word_graph as app_build
        from analysis import build_word_graph as analysis_build, tokenize_pt

        user_msgs = _get_user_messages()
        token_sequences = [tokenize_pt(msg) for msg in user_msgs if tokenize_pt(msg)]

        G_app = app_build(token_sequences, min_edge_weight=1, max_nodes=500)
        G_analysis = analysis_build(token_sequences, min_edge_weight=1)

        for node in G_app.nodes():
            app_count = G_app.nodes[node].get("count", 0)
            analysis_count = G_analysis.nodes[node].get("count", 0)
            assert app_count == analysis_count, (
                f"'{node}': app={app_count}, analysis={analysis_count}"
            )
