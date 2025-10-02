# Guia de Testes

## Executando Testes
```bash
# Todos os testes
./scripts/gates-v6.sh

# Testes específicos por padrão
./scripts/test-routing.sh
./scripts/test-parallelization.sh
./scripts/test-memory-management.sh

# Com cobertura de código
pytest --cov=src tests/
```

## Estrutura de Testes
```
tests/
├── unit/
│   ├── test_router_agent.py
│   └── test_parallel_processor.py
├── integration/
│   └── test_pattern_integration.py
└── performance/
    └── test_load.py
```

## Benchmarks de Performance
- **Routing**: < 100ms por requisição
- **Parallelization**: Escalamento linear para 10 tarefas concorrentes
- **Memory**: < 1MB por sessão
