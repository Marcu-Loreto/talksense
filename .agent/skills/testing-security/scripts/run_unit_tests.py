import os
import subprocess
import sys
import json

def run_pytest(test_path="tests"):
    """Runs pytest and returns the results as a dictionary."""
    if not os.path.exists(test_path):
        return {"status": "error", "message": f"Path '{test_path}' not found."}
    
    cmd = [sys.executable, "-m", "pytest", test_path, "--json-report", "--json-report-file=report.json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        # Check if report.json was created
        if os.path.exists("report.json"):
            with open("report.json", "r") as f:
                return json.load(f)
        return {"status": "error", "stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "tests"
    results = run_pytest(path)
    print(json.dumps(results, indent=2))
