# Memória do Trabalho (para retomar conversa)

Este arquivo registra o que foi feito no repositório **LicitacoesMedcal** durante esta sessão, para que futuras interações possam se basear nele (já que o assistente não acessa conversas antigas).

## Objetivos acordados

- Melhorar o sistema para:
  - **Observabilidade total** (logs, status, histórico por run, erros completos, sem `except:` silencioso).
  - **Confiabilidade de coleta** (retentativas, dedupe, estabilidade em background/threads).
  - **Financeiro sem “caixa preta”** (trilha de auditoria, validações e reconciliação mais confiável).
- **Não mexer** por enquanto no link hardcoded no WhatsApp (dev tunnel), deixando para depois.
- Migrar a IA para **OpenRouter-only** (remover Gemini) se OpenRouter cumprir as necessidades.

## Principais mudanças implementadas

### 1) Observabilidade (logs e erros visíveis)

- Criado logger central:
  - `LicitacoesMedcal/modules/utils/logging_config.py`
  - Padroniza formato e evita múltiplos handlers duplicados.
- Substituições/ajustes de prints e `except:` silenciosos em pontos críticos:
  - `LicitacoesMedcal/agent/analyze_service.py` (logs com `exc_info`)
  - `LicitacoesMedcal/agent/orchestrator.py` (logs do pipeline)
  - `LicitacoesMedcal/agent/scrape_service.py` (logs + retentativas)
  - `LicitacoesMedcal/modules/core/background_search.py` (logs + remove `estados=[...]` mutável)
  - `LicitacoesMedcal/modules/core/search_engine.py` (logs em vez de `print`, e `except:` -> `except Exception`)

### 2) Confiabilidade em execução concorrente (SQLite + threads)

Para reduzir “database is locked” e melhorar robustez com threads/background:

- Banco principal:
  - `LicitacoesMedcal/modules/database/database.py`
  - Engine com `check_same_thread=False`, `timeout=30`, `pool_pre_ping=True`
  - PRAGMAs no connect: `WAL`, `synchronous=NORMAL`, `busy_timeout=5000`
- Banco financeiro (ativo e histórico):
  - `LicitacoesMedcal/modules/finance/database.py`
  - Mesma estratégia de engine + PRAGMAs para `engine` e `engine_hist`

### 3) Financeiro “sem caixa preta” (auditoria)

- Criada tabela de auditoria:
  - `LicitacoesMedcal/modules/finance/bank_models.py` adiciona `FinanceAuditLog`
- Criado helper de auditoria:
  - `LicitacoesMedcal/modules/finance/audit.py`
- Importação grava evento de auditoria:
  - `LicitacoesMedcal/modules/finance/extrato_parser.py` chama `log_finance_event(...)`
  - `LicitacoesMedcal/modules/finance/historico_importer.py` passa `fonte`/arquivo para a auditoria

### 4) Filtros: remover itens fora do interesse (exemplos fornecidos)

Inseridos termos negativos adicionais para cortar ruído (gramados, bombas submersas, audiometria/fono, fisioterapia/inaloterapia, gesso/gipsita, elevadores/OTIS, insumos agropecuários/sementes):

- `LicitacoesMedcal/modules/scrapers/pncp_client.py`

### 5) Bug fix real encontrado

- Corrigido `NameError: Iterable` no import do notifier do agente:
  - `LicitacoesMedcal/agent/notifier.py` (importou `Iterable` do `typing`)

### 6) IA OpenRouter-only (Gemini removido)

Motivação: erros 429/quota do Gemini; decisão do usuário: remover Gemini e usar apenas OpenRouter.

- Refeito `ai_config.py` para **OpenRouter-only**:
  - `LicitacoesMedcal/modules/ai/ai_config.py`
  - Mantém `get_model()` e `UnifiedAIModel` (agora sem fallback).
  - `configure_genai()` virou stub (compatibilidade), mas não faz nada.
- Removida dependência do Gemini do enrich dos diários:
  - `LicitacoesMedcal/modules/scrapers/external_scrapers.py` usa `get_model()`
- Financeiro (IA SQL) ficou OpenRouter-only:
  - `LicitacoesMedcal/modules/finance/finance_ai.py` removeu provedor Gemini/`gemini_api_key`
- Validador IA e mensagens atualizadas:
  - `LicitacoesMedcal/modules/ai/licitacao_validator.py`
  - `LicitacoesMedcal/modules/ai/smart_analyzer.py`
  - `LicitacoesMedcal/modules/ai/ai_helper.py`
- Deep analyzer removeu dependência Gemini:
  - `LicitacoesMedcal/modules/core/deep_analyzer.py`
- Matcher do catálogo sem embeddings Gemini:
  - `LicitacoesMedcal/modules/ai/improved_matcher.py` foi reescrito para:
    - `find_matches`: fuzzy/keywords (sem embeddings)
    - `verify_match`: validação via OpenRouter (LLM)
- Dashboard atualizado:
  - `LicitacoesMedcal/dashboard.py` removeu inicialização Gemini e UI de “Gemini API Key”
  - Configuração de IA agora só exibe OpenRouter
- Scripts de migração ajustados:
  - `LicitacoesMedcal/scripts/migrate_db.py` cria placeholder de `openrouter_api_key`
  - `LicitacoesMedcal/scripts/migrate_db_direct.py` idem
- Docs e env:
  - `LicitacoesMedcal/docs/GUIA_BACKUP_SINCRONIZACAO.md` agora usa `OPENROUTER_API_KEY`
  - `LicitacoesMedcal/.env` trocado para `OPENROUTER_API_KEY=`
- Dependências:
  - `LicitacoesMedcal/requirements.txt` removeu `google-generativeai`

## O que ficou intencionalmente para depois

- **Link hardcoded** na notificação de WhatsApp no background (dev tunnel): não mexido por decisão do usuário.
- **Persistência da análise profunda**: foi identificado risco de conflito (campo `Licitacao.comentarios` sendo usado para texto e também para JSON/cache em algumas rotas). Não foi migrado ainda (ideal: coluna própria ou tabela).
- **Higiene do repositório**: foi identificado que podem existir arquivos locais/gerados versionados (ex.: `__pycache__`, `.claude/settings.local.json`, `.env`, caches/data e `.xlsx`). Não foi feita limpeza/`git rm --cached` nesta etapa.

## Como configurar/rodar (estado atual)

- Rodar UI:
  - `streamlit run dashboard.py` dentro da pasta `LicitacoesMedcal`
- IA:
  - Configurar `openrouter_api_key` em “Configurações” no dashboard, ou via env `OPENROUTER_API_KEY`.
- Compilação/import básico (cheque rápido):
  - `python3 -m compileall -q LicitacoesMedcal`

## Próximos passos recomendados (prioridade alta)

1) Consolidar pipeline (evitar duplicação entre `agent/*` e `modules/core/search_engine.py`).
2) Resolver a persistência do “deep analysis” (não usar `comentarios` para múltiplas finalidades).
3) Endurecer ainda mais dedupe/retentativas (principalmente diários/PDF) e registrar métricas por run.
4) Financeiro: criar relatórios de divergência/reconciliação e tela/rotina de “auditoria por import”.


---

## Sessão de 22/12/2024

### 7) Timeouts da API PNCP aumentados

Para mitigar `Read timed out` frequentes da API PNCP:

- `modules/scrapers/pncp_client.py`:
  - Busca principal: 30s → **45s**
  - Busca de itens: 10s → **30s**
  - Busca de arquivos/ID: 10s → **20s**

### 8) Filtros negativos expandidos

Adicionados termos para bloquear itens irrelevantes que passavam:

- **Veículos/Viaturas**: VIATURA, L200, HILUX, MITSUBISHI, TOYOTA, etc.
- **Construção**: GUINCHO, POLITRIZ, BETONEIRA, RETROESCAVADEIRA
- **Agrícola**: RANCHO, PLANTIO, GRAMÍNEO, IRRIGAÇÃO
- **Hidrossanitário**: HIDROSSANITÁRIO, ENCANAMENTO, TUBULAÇÃO
- **Eventos**: CARNAVAL, SÃO JOÃO, TRIO ELÉTRICO
- **Militar**: COMANDO DO EXÉRCITO, QUARTEL, BATALHÃO
- **Documentos**: PELÍCULA DE SEGURANÇA, CIN, CARTEIRA DE IDENTIFICAÇÃO
- **Copiadoras**: COPIADORA, MULTIFUNCIONAL
- **Diabéticos**: INSULINA, GLICOSÍMETRO (fora do escopo lab)
- **Elétrica predial**: GRUPO GERADOR, SUBESTAÇÃO, SPDA
- **Funerária**: URNA FUNERÁRIA, TRASLADO DE CORPO
- **Serviços de pessoal**: GARÇOM, COPEIRO, PORTEIRO, OFFICE BOY, MEI

Também corrigidos termos genéricos que bloqueavam itens legítimos:
- `ELÉTRICO` → `INSTALAÇÃO ELÉTRICA`, `REDE ELÉTRICA`
- `HIDRÁULICO` → `INSTALAÇÃO HIDRÁULICA`
- `SANITÁRIO` → `ESGOTO SANITÁRIO`

### 9) Cache de notificações WhatsApp (anti-spam)

Problema: ao apagar o banco de dados, notificações repetiam para licitações já enviadas.

Solução:
- Criado `modules/utils/notification_cache.py`:
  - Cache persistente em JSON (`data/whatsapp_notifications_sent.json`)
  - Rastreia IDs de licitações já notificadas por data
  - Independente do banco SQLite principal
- Integrado em `modules/core/search_engine.py`:
  - Verifica `notification_cache.was_already_sent()` antes de enviar
  - Grava `notification_cache.mark_as_sent()` após sucesso

### 10) Notificação "Busca Concluída" desabilitada

Para economizar quota diária do CallMeBot:
- `modules/core/background_search.py`: chamada `_notify_completion()` comentada
- Agora só envia notificações para **licitações reais** encontradas

### 11) Backup e Restore do Sistema (Export/Import)

Criada funcionalidade para exportar/importar todos os dados do sistema em um único arquivo ZIP:

- `modules/utils/system_backup.py`:
  - `export_backup()`: cria ZIP com todos os bancos e arquivos de dados
  - `import_backup()`: extrai ZIP e substitui dados locais
  - Força checkpoint WAL antes de exportar (dados atualizados)

- UI em `dashboard.py` (aba Configurações):
  - Botão "Gerar Backup" com download direto
  - Upload de arquivo ZIP para restauração
  - Lista de backups anteriores

Arquivos incluídos no backup:
- `data/medcal.db`, `data/financeiro.db`, `data/financeiro_historico.db`
- `data/catalogo_produtos.json`, `data/whatsapp_notifications_sent.json`
- Caches de embeddings e distância
