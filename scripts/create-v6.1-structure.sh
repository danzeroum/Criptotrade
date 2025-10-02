#!/usr/bin/env bash
set -euo pipefail

echo "🏗️ Criando estrutura BuildToValue v6.1..."

# Estrutura de Agentes Avançados
mkdir -p src/{agents,chains,consensus,evaluation,hitl,memory,orchestration,parallel,planning,protocols,routing,safety,tools/sandbox}

# Estrutura de Testes
mkdir -p tests/{unit,integration,e2e,performance,security}

# Estrutura de Configuração
mkdir -p config/{agents,prompts,tools,memory}

# Estrutura de Monitoramento
mkdir -p monitoring/{dashboards,alerts,reports}

# Estrutura de Documentação
mkdir -p docs/{agents,patterns,security,operations}

cat > config/agents/constitution.yaml <<'YAML'
# Constituição dos Agentes - Define comportamento, limites e capacidades
version: 6.1
agents:
  architect:
    capabilities: [planning, consensus, memory]
    autonomy_level: 2
    tools: [architecture_analyzer, adr_generator]
  developer:
    capabilities: [implementation, testing, debugging]
    autonomy_level: 1
    tools: [code_generator, test_generator, debugger]
  auditor:
    capabilities: [security, compliance, quality]
    autonomy_level: 3
    tools: [security_scanner, compliance_checker]
YAML

echo "✅ Estrutura v6.1 criada!"
