"""
Testes funcionais para o fluxo de sentimento:
- analysis.py: analisar_sentimento, score_from_label, tokenize_pt
- database.py: update_metadata, get_messages_without_sentiment
- api.py: construção de sentiment_metadata
- app.py: _score_from_label, integração de metadata
- pages/1_Dashboard_Insights.py: mapeamento de sessões por usuário
"""

import json
import sys
import os
import types
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

# ═══════════════════════════════════════════════════════════════
# FIXTURES E HELPERS
# ═══════════════════════════════════════════════════════════════

def _fake_openai_response(label="positivo", confidence=0.85, emotions=None, reason="teste"):
    """Simula resposta da OpenAI para análise de sentimento."""
    emotions = emotions or ["alegria"]
    content = json.dumps({
        "label": label,
        "confidence": confidence,
        "emotions": emotions,
        "reason": reason,
    })
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ═══════════════════════════════════════════════════════════════
# 1. TESTES analysis.py
# ═══════════════════════════════════════════════════════════════

class TestAnalysisSentimento:
    """Testes da função analisar_sentimento em analysis.py"""

    @patch("analysis.client")
    def test_sentimento_positivo(self, mock_client):
        from analysis import analisar_sentimento
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            "positivo", 0.92, ["alegria"], "Mensagem positiva"
        )
        result = analisar_sentimento("Estou muito feliz com o atendimento!")
        assert result["label"] == "positivo"
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["emotions"], list)
        assert len(result["reason"]) > 0

    @patch("analysis.client")
    def test_sentimento_negativo(self, mock_client):
        from analysis import analisar_sentimento
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            "negativo", 0.88, ["frustração"], "Reclamação"
        )
        result = analisar_sentimento("Péssimo atendimento, estou muito insatisfeito")
        assert result["label"] == "negativo"
        assert result["confidence"] == 0.88

    @patch("analysis.client")
    def test_sentimento_neutro(self, mock_client):
        from analysis import analisar_sentimento
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            "neutro", 0.6, [], "Mensagem informativa"
        )
        result = analisar_sentimento("Qual o horário de funcionamento?")
        assert result["label"] == "neutro"

    @patch("analysis.client")
    def test_sentimento_fallback_on_error(self, mock_client):
        """Se a API falhar, deve retornar neutro com confidence 0."""
        from analysis import analisar_sentimento
        mock_client.chat.completions.create.side_effect = Exception("API offline")
        result = analisar_sentimento("Qualquer texto")
        assert result["label"] == "neutro"
        assert result["confidence"] == 0.0
        assert "Erro" in result["reason"] or "Falha" in result["reason"]

    @patch("analysis.client")
    def test_sentimento_label_invalido_vira_neutro(self, mock_client):
        """Label fora do esperado deve ser normalizado para neutro."""
        from analysis import analisar_sentimento
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            "feliz", 0.9  # label inválido
        )
        result = analisar_sentimento("Texto qualquer")
        assert result["label"] == "neutro"

    @patch("analysis.client")
    def test_sentimento_confidence_clamped(self, mock_client):
        """Confidence fora de [0,1] deve ser clamped."""
        from analysis import analisar_sentimento
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            "positivo", 1.5
        )
        result = analisar_sentimento("Texto")
        assert result["confidence"] <= 1.0


class TestScoreFromLabel:
    """Testes da função score_from_label em analysis.py"""

    def test_positivo_score(self):
        from analysis import score_from_label
        score = score_from_label("positivo", 0.9)
        assert score == 0.9

    def test_negativo_score(self):
        from analysis import score_from_label
        score = score_from_label("negativo", 0.8)
        assert score == -0.8

    def test_neutro_score_zero(self):
        from analysis import score_from_label
        score = score_from_label("neutro", 0.99)
        assert score == 0.0

    def test_score_boundaries(self):
        from analysis import score_from_label
        assert score_from_label("positivo", 0.0) == 0.0
        assert score_from_label("positivo", 1.0) == 1.0
        assert score_from_label("negativo", 1.0) == -1.0


class TestTokenizePt:
    """Testes da tokenização PT-BR em analysis.py"""

    def test_remove_stopwords(self):
        from analysis import tokenize_pt
        tokens = tokenize_pt("eu estou muito feliz com isso")
        assert "eu" not in tokens
        assert "com" not in tokens
        assert "feliz" in tokens

    def test_remove_palavras_curtas(self):
        from analysis import tokenize_pt
        tokens = tokenize_pt("a de um os no")
        assert len(tokens) == 0

    def test_lowercase(self):
        from analysis import tokenize_pt
        tokens = tokenize_pt("ATENDIMENTO Excelente")
        assert "atendimento" in tokens
        assert "excelente" in tokens

    def test_texto_vazio(self):
        from analysis import tokenize_pt
        tokens = tokenize_pt("")
        assert tokens == []


# ═══════════════════════════════════════════════════════════════
# 2. TESTES app.py — _score_from_label
# ═══════════════════════════════════════════════════════════════

class TestAppScoreFromLabel:
    """Testes da função _score_from_label no app.py (já existiam parcialmente)."""

    def test_positivo(self):
        from app import _score_from_label
        assert _score_from_label("positivo", 0.9) > 0

    def test_negativo(self):
        from app import _score_from_label
        assert _score_from_label("negativo", 0.9) < 0

    def test_neutro(self):
        from app import _score_from_label
        assert _score_from_label("neutro", 0.5) == 0

    def test_symmetry(self):
        from app import _score_from_label
        pos = _score_from_label("positivo", 0.7)
        neg = _score_from_label("negativo", 0.7)
        assert abs(pos + neg) < 0.001  # simétricos


# ═══════════════════════════════════════════════════════════════
# 3. TESTES sentiment_metadata construction (api.py pattern)
# ═══════════════════════════════════════════════════════════════

class TestSentimentMetadataConstruction:
    """Testa a lógica de construção do sentiment_metadata usada em api.py e app.py."""

    def _build_sentiment_metadata(self, resultado):
        """Replica a lógica de construção do metadata de sentimento."""
        from analysis import score_from_label
        label = resultado.get("label", "neutro")
        confidence = float(resultado.get("confidence", 0.0))
        score = score_from_label(label, confidence)
        emotions = resultado.get("emotions", [])
        return {
            "sentimento": label,
            "confianca": str(confidence),
            "emocao": emotions[0] if emotions else "nenhuma",
            "score": str(score),
        }

    def test_metadata_positivo(self):
        meta = self._build_sentiment_metadata({
            "label": "positivo", "confidence": 0.85, "emotions": ["alegria"]
        })
        assert meta["sentimento"] == "positivo"
        assert meta["confianca"] == "0.85"
        assert meta["emocao"] == "alegria"
        assert float(meta["score"]) > 0

    def test_metadata_negativo(self):
        meta = self._build_sentiment_metadata({
            "label": "negativo", "confidence": 0.7, "emotions": ["frustração"]
        })
        assert meta["sentimento"] == "negativo"
        assert float(meta["score"]) < 0

    def test_metadata_sem_emocoes(self):
        meta = self._build_sentiment_metadata({
            "label": "neutro", "confidence": 0.5, "emotions": []
        })
        assert meta["emocao"] == "nenhuma"

    def test_metadata_types_are_strings(self):
        """Todos os valores do metadata devem ser strings para JSONB."""
        meta = self._build_sentiment_metadata({
            "label": "positivo", "confidence": 0.9, "emotions": ["alegria"]
        })
        assert isinstance(meta["confianca"], str)
        assert isinstance(meta["score"], str)
        assert isinstance(meta["sentimento"], str)
        assert isinstance(meta["emocao"], str)

    def test_metadata_merge_with_existing(self):
        """Testa que o spread operator funciona corretamente."""
        existing = {"user_id": "123", "source": "api"}
        sentiment = self._build_sentiment_metadata({
            "label": "positivo", "confidence": 0.8, "emotions": ["alegria"]
        })
        merged = {**existing, **sentiment}
        assert merged["user_id"] == "123"
        assert merged["source"] == "api"
        assert merged["sentimento"] == "positivo"
        assert len(merged) == 6  # 2 existing + 4 sentiment


# ═══════════════════════════════════════════════════════════════
# 4. TESTES database.py — novos métodos
# ═══════════════════════════════════════════════════════════════

class TestDatabaseUpdateMetadata:
    """Testa Database.update_metadata (mock do PostgreSQL)."""

    @patch("database.get_connection")
    @patch("database.put_connection")
    def test_update_metadata_success(self, mock_put, mock_get):
        from database import Database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_conn

        result = Database.update_metadata(42, {"sentimento": "positivo", "score": "0.9"})

        assert result is True
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args
        assert "UPDATE messages" in sql_call[0][0]
        assert "metadata" in sql_call[0][0]
        mock_conn.commit.assert_called_once()

    @patch("database.get_connection")
    def test_update_metadata_no_connection(self, mock_get):
        from database import Database
        mock_get.return_value = None
        result = Database.update_metadata(1, {"sentimento": "positivo"})
        assert result is False

    @patch("database.get_connection")
    @patch("database.put_connection")
    def test_update_metadata_db_error_rollback(self, mock_put, mock_get):
        from database import Database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_conn

        result = Database.update_metadata(1, {"sentimento": "positivo"})

        assert result is False
        mock_conn.rollback.assert_called_once()


class TestDatabaseGetMessagesWithoutSentiment:
    """Testa Database.get_messages_without_sentiment."""

    @patch("database.get_connection")
    @patch("database.put_connection")
    def test_returns_messages_without_sentiment(self, mock_put, mock_get):
        from database import Database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "content": "Olá, preciso de ajuda"},
            {"id": 2, "content": "Meu pedido atrasou"},
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_conn

        result = Database.get_messages_without_sentiment(limit=10)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["content"] == "Meu pedido atrasou"

    @patch("database.get_connection")
    def test_no_connection_returns_empty(self, mock_get):
        from database import Database
        mock_get.return_value = None
        result = Database.get_messages_without_sentiment()
        assert result == []

    @patch("database.get_connection")
    @patch("database.put_connection")
    def test_sql_filters_correctly(self, mock_put, mock_get):
        """Verifica que a query filtra por role='user' e sentimento NULL."""
        from database import Database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_conn

        Database.get_messages_without_sentiment(limit=50)

        sql = mock_cursor.execute.call_args[0][0]
        assert "role = 'user'" in sql
        assert "sentimento" in sql
        assert "IS NULL" in sql


# ═══════════════════════════════════════════════════════════════
# 5. TESTES dashboard — mapeamento sessão → usuário
# ═══════════════════════════════════════════════════════════════

class TestDashboardSessionMapping:
    """Testa a lógica de mapeamento session_id → nome do usuário."""

    def _build_mapping(self, df):
        """Replica a lógica do dashboard para construir o mapa de opções."""
        import pandas as pd
        _sessoes_usuarios = df.groupby("session_id")["usuario"].first().reset_index()
        _contagem_nomes = _sessoes_usuarios["usuario"].value_counts()
        _opcoes_mapa = {}
        for _, row in _sessoes_usuarios.iterrows():
            nome = row["usuario"]
            sid = row["session_id"]
            if _contagem_nomes.get(nome, 0) > 1:
                label = f"{nome} ({sid[:12]}…)" if len(sid) > 12 else f"{nome} ({sid})"
            else:
                label = nome
            _opcoes_mapa[label] = sid
        return _opcoes_mapa

    def test_nome_unico(self):
        import pandas as pd
        df = pd.DataFrame({
            "session_id": ["sess_001", "sess_002"],
            "usuario": ["Maria", "João"],
        })
        mapa = self._build_mapping(df)
        assert "Maria" in mapa
        assert "João" in mapa
        assert mapa["Maria"] == "sess_001"

    def test_nomes_duplicados_incluem_session_id(self):
        import pandas as pd
        df = pd.DataFrame({
            "session_id": ["sess_001", "sess_002"],
            "usuario": ["Desconhecido", "Desconhecido"],
        })
        mapa = self._build_mapping(df)
        # Ambos devem ter o session_id no label
        labels = list(mapa.keys())
        assert len(labels) == 2
        for label in labels:
            assert "Desconhecido" in label
            assert "(" in label  # contém session_id

    def test_session_id_longo_truncado(self):
        import pandas as pd
        long_sid = "abcdefghijklmnopqrstuvwxyz"
        df = pd.DataFrame({
            "session_id": [long_sid, "sess_002"],
            "usuario": ["Desconhecido", "Desconhecido"],
        })
        mapa = self._build_mapping(df)
        for label in mapa.keys():
            if long_sid[:12] in label:
                assert "…" in label  # truncado

    def test_mapa_vazio(self):
        import pandas as pd
        df = pd.DataFrame({"session_id": [], "usuario": []})
        mapa = self._build_mapping(df)
        assert mapa == {}


# ═══════════════════════════════════════════════════════════════
# 6. TESTES de filtro (máscara) do dashboard
# ═══════════════════════════════════════════════════════════════

class TestDashboardFilters:
    """Testa a lógica de filtragem por data e sessão."""

    def _apply_mask(self, df, d_ini, d_fim, sessao_selecionada="Todas as Conversas"):
        import pandas as pd
        mask = (
            (df["datahora"].dt.date >= d_ini)
            & (df["datahora"].dt.date <= d_fim)
        )
        if sessao_selecionada != "Todas as Conversas":
            mask = mask & (df["session_id"] == sessao_selecionada)
        return df.loc[mask].copy()

    def test_filtro_por_data(self):
        import pandas as pd
        from datetime import date
        df = pd.DataFrame({
            "session_id": ["s1", "s1", "s1"],
            "datahora": pd.to_datetime(["2025-01-01", "2025-06-15", "2025-12-31"]),
            "sentimento": ["positivo", "neutro", "negativo"],
        })
        result = self._apply_mask(df, date(2025, 6, 1), date(2025, 6, 30))
        assert len(result) == 1
        assert result.iloc[0]["sentimento"] == "neutro"

    def test_filtro_por_sessao(self):
        import pandas as pd
        from datetime import date
        df = pd.DataFrame({
            "session_id": ["s1", "s2", "s1"],
            "datahora": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"]),
            "sentimento": ["positivo", "neutro", "negativo"],
        })
        result = self._apply_mask(df, date(2025, 1, 1), date(2025, 12, 31), "s2")
        assert len(result) == 1
        assert result.iloc[0]["session_id"] == "s2"

    def test_todas_conversas(self):
        import pandas as pd
        from datetime import date
        df = pd.DataFrame({
            "session_id": ["s1", "s2"],
            "datahora": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "sentimento": ["positivo", "negativo"],
        })
        result = self._apply_mask(df, date(2025, 1, 1), date(2025, 12, 31))
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════
# 7. TESTES de integração end-to-end (mock)
# ═══════════════════════════════════════════════════════════════

class TestEndToEndSentimentFlow:
    """Testa o fluxo completo: análise → metadata → banco → dashboard."""

    @patch("analysis.client")
    def test_full_flow_positive_message(self, mock_client):
        """Simula mensagem positiva passando por todo o pipeline."""
        from analysis import analisar_sentimento, score_from_label

        # 1. Análise de sentimento
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            "positivo", 0.92, ["satisfação"], "Cliente satisfeito"
        )
        resultado = analisar_sentimento("Adorei o atendimento, muito obrigado!")

        # 2. Construção do metadata
        label = resultado["label"]
        confidence = resultado["confidence"]
        score = score_from_label(label, confidence)
        emotions = resultado["emotions"]

        metadata = {
            "origem": "app_streamlit_chat",
            "user_name": "Maria",
            "sentimento": label,
            "confianca": str(confidence),
            "emocao": emotions[0] if emotions else "nenhuma",
            "score": str(score),
        }

        # 3. Verifica que o metadata está completo para o banco
        assert metadata["sentimento"] == "positivo"
        assert float(metadata["confianca"]) == 0.92
        assert float(metadata["score"]) > 0
        assert metadata["emocao"] == "satisfação"
        assert metadata["user_name"] == "Maria"

        # 4. Simula leitura do dashboard (COALESCE)
        # Se metadata->>'sentimento' existe, retorna o valor real
        sentimento_dashboard = metadata.get("sentimento") or "neutro"
        assert sentimento_dashboard == "positivo"  # NÃO mais "neutro"!

    @patch("analysis.client")
    def test_full_flow_api_error_graceful(self, mock_client):
        """Se a API falhar, o metadata deve ficar vazio mas não quebrar."""
        from analysis import analisar_sentimento

        mock_client.chat.completions.create.side_effect = Exception("timeout")

        sentiment_metadata = {}
        try:
            resultado = analisar_sentimento("Texto qualquer")
            label = resultado.get("label", "neutro")
            confidence = float(resultado.get("confidence", 0.0))
            # Mesmo com erro, analisar_sentimento retorna fallback
            sentiment_metadata = {
                "sentimento": label,
                "confianca": str(confidence),
            }
        except Exception:
            pass  # sentiment_metadata fica vazio

        # O metadata deve ter o fallback neutro, não ficar vazio
        assert sentiment_metadata.get("sentimento") == "neutro"
        assert sentiment_metadata.get("confianca") == "0.0"
