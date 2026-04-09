"""
Migração: PostgreSQL → Neo4j Aura
Lê todas as mensagens do PostgreSQL, tokeniza e popula o grafo no Neo4j.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database import Database, DATABASE_AVAILABLE, get_connection, put_connection
from analysis import tokenize_pt
from neo4j_graph import (
    NEO4J_AVAILABLE, _driver, salvar_tokens_mensagem, obter_estatisticas, init_schema
)


def carregar_mensagens_pg():
    """Carrega todas as mensagens de usuário do PostgreSQL."""
    conn = get_connection()
    if not conn:
        print("❌ Sem conexão PostgreSQL")
        return []

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, session_id, content, 
                       COALESCE(metadata->>'user_name', 'Desconhecido') as user_name
                FROM messages 
                WHERE role = 'user' AND content IS NOT NULL AND content != ''
                ORDER BY created_at ASC
            """)
            rows = cur.fetchall()
            return [
                {"id": r[0], "session_id": r[1], "content": r[2], "user_name": r[3]}
                for r in rows
            ]
    except Exception as e:
        print(f"❌ Erro ao ler PostgreSQL: {e}")
        return []
    finally:
        put_connection(conn)


def migrar():
    print("=" * 60)
    print("  MIGRAÇÃO PostgreSQL → Neo4j Aura")
    print("=" * 60)

    # Verifica conexões
    if not DATABASE_AVAILABLE:
        print("❌ PostgreSQL não disponível. Verifique o .env")
        return

    if not NEO4J_AVAILABLE:
        print("❌ Neo4j não disponível. Verifique o .env")
        return

    print(f"✅ PostgreSQL conectado")
    print(f"✅ Neo4j conectado")

    # Stats antes
    stats = obter_estatisticas()
    print(f"\n📊 Neo4j antes: {stats['nodes']} nós, {stats['edges']} arestas")

    # Carrega mensagens
    mensagens = carregar_mensagens_pg()
    print(f"\n📥 {len(mensagens)} mensagens encontradas no PostgreSQL")

    if not mensagens:
        print("Nada para migrar.")
        return

    # Processa
    total = len(mensagens)
    sucesso = 0
    tokens_total = 0

    for i, msg in enumerate(mensagens):
        tokens = tokenize_pt(msg["content"])
        if not tokens:
            continue

        ok = salvar_tokens_mensagem(
            tokens=tokens,
            session_id=msg["session_id"],
            window_size=3,
        )

        if ok:
            sucesso += 1
            tokens_total += len(tokens)

        # Progresso a cada 10 mensagens
        if (i + 1) % 10 == 0 or i == total - 1:
            pct = ((i + 1) / total) * 100
            print(f"  [{pct:5.1f}%] {i+1}/{total} mensagens | {sucesso} com tokens | {tokens_total} tokens")

    # Stats depois
    stats = obter_estatisticas()
    print(f"\n📊 Neo4j depois: {stats['nodes']} nós, {stats['edges']} arestas")
    print(f"\n✅ Migração concluída: {sucesso} mensagens processadas, {tokens_total} tokens inseridos")


if __name__ == "__main__":
    migrar()
