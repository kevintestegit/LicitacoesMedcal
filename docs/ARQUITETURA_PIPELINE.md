# Arquitetura do Pipeline de Busca - LicitacoesMedcal

## Visão Geral

O sistema possui duas camadas de pipeline de busca que compartilham componentes centrais:

```
┌─────────────────────────────────────────────────────────────────┐
│                         CAMADA DE SERVIÇOS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────────────────┐  │
│  │    agent/        │         │    modules/core/             │  │
│  │    orchestrator  │         │    search_engine             │  │
│  │    (CLI/Headless)│         │    (Dashboard/Background)    │  │
│  └────────┬─────────┘         └─────────────┬────────────────┘  │
│           │                                  │                   │
│           └──────────────┬───────────────────┘                   │
│                          │                                       │
│                          ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              CAMADA COMPARTILHADA (Core)                  │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  modules/core/opportunity_collector.py                    │  │
│  │  modules/scrapers/pncp_client.py                          │  │
│  │  modules/scrapers/external_scrapers.py                    │  │
│  │  modules/ai/improved_matcher.py                           │  │
│  │  modules/ai/semantic_filter.py                            │  │
│  │  modules/database/database.py                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Fluxo de Dados

### 1. Dashboard/Background (search_engine.py)
```
1. SearchEngine.execute_full_search()
   ↓
2. collect_opportunities() → coleta PNCP + diários
   ↓
3. SearchEngine.run_search_pipeline()
   ├── Salva/atualiza licitações no banco
   ├── match_itens() → cruza com catálogo
   └── enviar_relatorio_whatsapp() → notifica matches
```

### 2. Agent CLI/Headless (orchestrator.py)
```
1. orchestrator.executar()
   ↓
2. scrape_service.coletar_licitacoes() → collect_opportunities()
   ↓
3. analyze_service.analisar_licitacao()
   ├── SemanticFilter → relevância
   ├── SemanticMatcher → match catálogo
   └── SmartAnalyzer → viabilidade IA
   ↓
4. decision.policy.aplicar_politica() → decisão final
```

## Componentes Compartilhados

| Módulo | Responsabilidade |
|--------|-----------------|
| `modules/core/opportunity_collector.py` | Coleta unificada PNCP + diários |
| `modules/scrapers/pncp_client.py` | Cliente API PNCP |
| `modules/scrapers/external_scrapers.py` | Scrapers FEMURN/FAMUP/etc |
| `modules/ai/improved_matcher.py` | Match fuzzy + IA com catálogo |
| `modules/ai/semantic_filter.py` | Filtro de relevância |
| `modules/database/database.py` | Modelos e sessão SQLAlchemy |

## Quando Usar Cada Camada

| Cenário | Usar |
|---------|------|
| Dashboard Streamlit interativo | `SearchEngine` |
| Busca automática em background | `SearchEngine` |
| Script CLI headless | `agent/orchestrator` |
| Processamento em lote | `agent/orchestrator` |

---
*Documentação criada em: 2025-12-23*
