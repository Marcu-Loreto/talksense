---
name: testing-security
description: "Create and execute unit tests and security assessments (guardrails, pentest, jailbreaks, prompt injections). Use this skill when the user wants to verify code correctness or probe an LLM-based system for vulnerabilities. It ensures high quality and safety by generating automated reports with pass/fail metrics in the 'testes/' folder."
---

# Testing and Security Skill

This skill allows Claude to act as a QA and Security Engineer. It focuses on functional correctness via unit tests and system safety via security probing.

## 🛠️ Main Objectives
1. **Unit Testing**: Generate and run unit tests for Python/FastAPI/Streamlit projects.
2. **Security Probing**: Execute "Red Teaming" attacks to test for:
   - **Jailbreaks**: Attempts to bypass system prompts or safety guardrails.
   - **Prompt Injections**: Malicious payloads hidden in user input.
   - **Data Exfiltration**: Attempts to leak sensitive metadata or environment variables.
3. **Reporting**: Generate a structured report in the `testes/` directory with detailed findings and a summary of success/failure percentages.

## 📋 Instructions

### 1. Environment Setup
- Before running tests, ensure the target environment is ready.
- If the `testes/` directory does not exist, create it.

### 2. Unit Testing Workflow
- Analyze the codebase to identify critical functions and logic.
- Use `pytest` for executing unit tests.
- Reference the `scripts/run_unit_tests.py` helper if available for discovery.
- Aim for high coverage of edge cases.

### 3. Security Testing Workflow
- **Guardrail Check**: Test if the system prompt can be bypassed by common techniques (e.g., "Ignore previous instructions", "DAN", "Payload splitting").
- **Injection Check**: Test if user-provided content can manipulate system logic.
- **Vulnerability Scan**: Use `scripts/security_scanner.py` for static analysis of dependencies and code patterns.

### 4. Report Generation
- Use the template at `assets/report_template.md`.
- Include:
  - Timestamp and Environment info.
  - Detailed test cases (with prompt/result).
  - Summary: Total Tests, Passed, Failed, Success Rate (%).
  - Mitigation Recommendations for each failure.

### 5. Best Practices
- **Do no harm**: Do not delete production data or shutdown services during testing.
- **Reproducibility**: Provide the exact payloads used for security tests.
- **Conciseness**: Keep the report professional and actionable.

## 📂 Bundled Resources
- `scripts/run_unit_tests.py`: Python script for automated `pytest` discovery.
- `scripts/security_scanner.py`: Script for security vulnerability checks.
- `assets/report_template.md`: Template for the final report.
