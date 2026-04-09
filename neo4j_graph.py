# neo4j_graph.py
"""
Integração com Neo4j Aura para grafo de palavras.
Persiste relações de coocorrência entre palavras no banco de grafos.
"""

import os
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

_driver = None
NEO4J_AVAILABLE = False

try:
    from neo4j import GraphDatabase
    if NEO4J_URI and NEO4J_PASSWORD:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        _driver.verify_connectivity()
        NEO4J_AVAILABLE = True
        print(f"✅ Neo4j Aura conectado: {NEO4J_URI[:40]}...")
    else:
        print("⚠️ Neo4j: URI ou PASSWORD não configurados no .env")
except Exception as e:
    print(f"❌ Neo4j indisponível: {e}")
    _driver = None
    NEO4J_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
# INICIALIZAÇÃO DO SCHEMA
# ═══════════════════════════════════════════════════════════════

def init_schema():
    """Cria constraints e índices no Neo4j."""
    if not _driver:
        return
    try:
        with _driver.session() as session:
            session.run(
                "CREATE CONSTRAINT word_unique IF NOT EXISTS "
                "FOR (w:Word) REQUIRE w.text IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT session_unique IF NOT EXISTS "
                "FOR (s:Session) REQUIRE s.session_id IS UNIQUE"
            )
        print("✅ Neo4j schema inicializado")
    except Exception as e:
        print(f"⚠️ Neo4j init_schema: {e}")


if NEO4J_AVAILABLE:
    try:
        init_schema()
    except Exception as e:
        print(f"⚠️ Neo4j schema falhou: {e}")


# ═══════════════════════════════════════════════════════════════
# PERSISTÊNCIA DO GRAFO DE PALAVRAS
# ═══════════════════════════════════════════════════════════════

def salvar_coocorrencias(
    token_sequences: List[List[str]],
    session_id: str = "global",
    window_size: int = 3,
):
    """
    Persiste tokens e coocorrências no Neo4j.
    - Cria/atualiza nós :Word com contagem
    - Cria/atualiza relações :COOCCURS com peso
    - Vincula palavras à sessão
    """
    if not _driver or not token_sequences:
        return False

    try:
        with _driver.session() as session:
            # Garante nó da sessão
            session.run(
                "MERGE (s:Session {session_id: $sid})",
                sid=session_id,
            )

            for seq in token_sequences:
                # Upsert de cada palavra
                for word in seq:
                    session.run(
                        """
                        MERGE (w:Word {text: $word})
                        ON CREATE SET w.count = 1
                        ON MATCH SET w.count = w.count + 1
                        WITH w
                        MERGE (s:Session {session_id: $sid})
                        MERGE (w)-[:APPEARS_IN]->(s)
                        """,
                        word=word,
                        sid=session_id,
                    )

                # Coocorrências com sliding window
                for i in range(len(seq)):
                    for j in range(i + 1, min(i + window_size, len(seq))):
                        a, b = seq[i], seq[j]
                        if a == b:
                            continue
                        # Ordena para evitar duplicatas direcionais
                        w1, w2 = sorted([a, b])
                        session.run(
                            """
                            MATCH (a:Word {text: $w1}), (b:Word {text: $w2})
                            MERGE (a)-[r:COOCCURS]-(b)
                            ON CREATE SET r.weight = 1, r.sessions = [$sid]
                            ON MATCH SET r.weight = r.weight + 1,
                                         r.sessions = CASE 
                                           WHEN NOT $sid IN r.sessions THEN r.sessions + $sid
                                           ELSE r.sessions
                                         END
                            """,
                            w1=w1,
                            w2=w2,
                            sid=session_id,
                        )
        return True
    except Exception as e:
        print(f"❌ Neo4j salvar_coocorrencias: {e}")
        return False


def salvar_tokens_mensagem(tokens: List[str], session_id: str = "global", window_size: int = 3):
    """Salva tokens de uma única mensagem (chamado a cada nova mensagem)."""
    if not tokens:
        return False
    return salvar_coocorrencias([tokens], session_id=session_id, window_size=window_size)


# ═══════════════════════════════════════════════════════════════
# CONSULTAS DO GRAFO
# ═══════════════════════════════════════════════════════════════

def obter_grafo_completo(session_id: Optional[str] = None, limit: int = 500) -> Optional[Dict]:
    """
    Retorna nós e arestas do Neo4j para renderização.
    Se session_id for informado, filtra palavras daquela sessão.
    Retorna: {"nodes": [{text, count}], "edges": [{source, target, weight}]}
    """
    if not _driver:
        return None

    try:
        with _driver.session() as session:
            if session_id:
                # Palavras da sessão específica
                result_nodes = session.run(
                    """
                    MATCH (w:Word)-[:APPEARS_IN]->(s:Session {session_id: $sid})
                    RETURN w.text AS text, w.count AS count
                    ORDER BY w.count DESC LIMIT $limit
                    """,
                    sid=session_id,
                    limit=limit,
                )
            else:
                result_nodes = session.run(
                    """
                    MATCH (w:Word)
                    RETURN w.text AS text, w.count AS count
                    ORDER BY w.count DESC LIMIT $limit
                    """,
                    limit=limit,
                )

            nodes = [{"text": r["text"], "count": r["count"]} for r in result_nodes]
            node_texts = {n["text"] for n in nodes}

            # Arestas entre os nós retornados (filtradas por sessão se aplicável)
            if session_id:
                result_edges = session.run(
                    """
                    MATCH (a:Word)-[r:COOCCURS]-(b:Word)
                    WHERE a.text IN $words AND b.text IN $words AND a.text < b.text
                      AND (r.sessions IS NULL OR $sid IN r.sessions)
                    RETURN a.text AS source, b.text AS target, r.weight AS weight
                    """,
                    words=list(node_texts),
                    sid=session_id,
                )
            else:
                result_edges = session.run(
                    """
                    MATCH (a:Word)-[r:COOCCURS]-(b:Word)
                    WHERE a.text IN $words AND b.text IN $words AND a.text < b.text
                    RETURN a.text AS source, b.text AS target, r.weight AS weight
                    """,
                    words=list(node_texts),
                )
            edges = [{"source": r["source"], "target": r["target"], "weight": r["weight"]} for r in result_edges]

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        print(f"❌ Neo4j obter_grafo_completo: {e}")
        return None


def obter_subgrafo(palavra_alvo: str, max_depth: int = 4, min_weight: int = 1) -> Optional[Dict]:
    """
    Retorna subgrafo centrado numa palavra alvo até max_depth de profundidade.
    """
    if not _driver or not palavra_alvo:
        return None

    try:
        with _driver.session() as session:
            result = session.run(
                """
                MATCH path = (start:Word {text: $alvo})-[:COOCCURS*1..""" + str(max_depth) + """]->(end:Word)
                WITH nodes(path) AS ns, relationships(path) AS rs
                UNWIND ns AS n
                WITH COLLECT(DISTINCT n) AS all_nodes, rs
                UNWIND all_nodes AS node
                WITH COLLECT(DISTINCT {text: node.text, count: node.count}) AS nodes, rs
                UNWIND rs AS rel
                WITH nodes, COLLECT(DISTINCT {
                    source: startNode(rel).text,
                    target: endNode(rel).text,
                    weight: rel.weight
                }) AS edges
                RETURN nodes, edges
                """,
                alvo=palavra_alvo,
            )
            record = result.single()
            if not record:
                # Tenta busca sem direção (COOCCURS é não-direcional)
                result2 = session.run(
                    """
                    MATCH (start:Word {text: $alvo})
                    CALL apoc.path.subgraphAll(start, {
                        relationshipFilter: 'COOCCURS',
                        maxLevel: $depth
                    }) YIELD nodes, relationships
                    UNWIND nodes AS n
                    WITH COLLECT({text: n.text, count: n.count}) AS ns, relationships
                    UNWIND relationships AS r
                    RETURN ns AS nodes, COLLECT({
                        source: startNode(r).text,
                        target: endNode(r).text,
                        weight: r.weight
                    }) AS edges
                    """,
                    alvo=palavra_alvo,
                    depth=max_depth,
                )
                record = result2.single()

            if not record:
                return None

            nodes = record["nodes"]
            edges = [e for e in record["edges"] if e["weight"] >= min_weight]
            return {"nodes": nodes, "edges": edges}
    except Exception as e:
        print(f"⚠️ Neo4j subgrafo via APOC falhou, usando BFS manual: {e}")
        return _subgrafo_bfs(palavra_alvo, max_depth, min_weight)


def _subgrafo_bfs(palavra_alvo: str, max_depth: int = 4, min_weight: int = 1) -> Optional[Dict]:
    """Fallback: BFS manual para obter subgrafo sem APOC."""
    if not _driver:
        return None
    try:
        with _driver.session() as session:
            # Busca vizinhos nível a nível
            visited = {palavra_alvo}
            frontier = {palavra_alvo}
            all_nodes = {}
            all_edges = []

            # Pega info do nó raiz
            r = session.run("MATCH (w:Word {text: $t}) RETURN w.count AS count", t=palavra_alvo)
            rec = r.single()
            if rec:
                all_nodes[palavra_alvo] = rec["count"]

            for _ in range(max_depth):
                if not frontier:
                    break
                result = session.run(
                    """
                    MATCH (a:Word)-[r:COOCCURS]-(b:Word)
                    WHERE a.text IN $frontier AND NOT b.text IN $visited
                    RETURN a.text AS source, b.text AS target, r.weight AS weight, b.count AS count
                    """,
                    frontier=list(frontier),
                    visited=list(visited),
                )
                new_frontier = set()
                for rec in result:
                    t = rec["target"]
                    new_frontier.add(t)
                    visited.add(t)
                    all_nodes[t] = rec["count"]
                    if rec["weight"] >= min_weight:
                        all_edges.append({"source": rec["source"], "target": t, "weight": rec["weight"]})
                frontier = new_frontier

            nodes = [{"text": t, "count": c} for t, c in all_nodes.items()]
            return {"nodes": nodes, "edges": all_edges}
    except Exception as e:
        print(f"❌ Neo4j _subgrafo_bfs: {e}")
        return None


def obter_estatisticas() -> Dict:
    """Retorna estatísticas do grafo."""
    if not _driver:
        return {"nodes": 0, "edges": 0}
    try:
        with _driver.session() as session:
            r1 = session.run("MATCH (w:Word) RETURN count(w) AS total")
            r2 = session.run("MATCH ()-[r:COOCCURS]-() RETURN count(r)/2 AS total")
            return {
                "nodes": r1.single()["total"],
                "edges": r2.single()["total"],
            }
    except Exception as e:
        print(f"❌ Neo4j stats: {e}")
        return {"nodes": 0, "edges": 0}
