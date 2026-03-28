import os
import re
import sys
import json

def scan_vulnerabilities(target_path="."):
    """Scans for basic security vulnerabilities in code."""
    vulnerabilities = []
    
    # Regex patterns for common security issues
    patterns = {
        "Hardcoded Secrets": r"(?:api_key|secret|password|token)\s*=\s*['\"][a-zA-Z0-9_-]{10,}['\"]",
        "SQL Injection risk": r"execute\(.*?\%.*?|execute\(.*?f['\"].*?\{",
        "Unsafe Deserialization": r"pickle\.load\(|yaml\.load\(",
        "OS Command Injection": r"os\.system\(|subprocess\.run\(.*?shell=True",
    }
    
    for root, dirs, files in os.walk(target_path):
        if ".venv" in root or "__pycache__" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            for name, pattern in patterns.items():
                                if re.search(pattern, line):
                                    vulnerabilities.append({
                                        "file": path,
                                        "line": i + 1,
                                        "vulnerability": name,
                                        "content": line.strip()
                                    })
                except Exception as e:
                    print(f"Error reading {path}: {e}")
    
    return vulnerabilities

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    results = scan_vulnerabilities(path)
    print(json.dumps(results, indent=2))
