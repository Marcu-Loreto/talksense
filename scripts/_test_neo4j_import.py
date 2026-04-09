import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

try:
    from neo4j_graph import (
        NEO4J_AVAILABLE,
        obter_grafo_completo,
        _subgrafo_bfs,
        obter_estatisticas,
    )
    print(f"NEO4J_AVAILABLE = {NEO4J_AVAILABLE}")
    stats = obter_estatisticas()
    print(f"Stats: {stats}")
    data = obter_grafo_completo(limit=5)
    if data:
        print(f"Nodes: {len(data['nodes'])}, Edges: {len(data['edges'])}")
    else:
        print("obter_grafo_completo returned None")
except Exception as e:
    print(f"IMPORT FAILED: {e}")
    import traceback
    traceback.print_exc()
