# LicitacoesMedcal
Sistema de busca de licitações - Medcal FARMA

## O que a Medcal concorre
- Modalidades: Pregão Eletrônico (6) e Dispensa/Compra Direta (8). Inexigibilidade só se muito aderente.
- Escopo: locação/comodato de equipamentos de análises clínicas (hematologia, bioquímica, coagulação, imunologia, ionograma, hormônios, gasometria/POCT) com fornecimento de reagentes e insumos; consumíveis laboratoriais (luvas, máscaras, tubos/coleta); manutenção preventiva associada aos equipamentos fornecidos.
- Não concorre: material odontológico, planos/serviços de saúde, obras/engenharia, TI genérica, vigilância/limpeza, viagens, veículos, combustíveis, construção civil, merenda etc.

## Como filtramos
- Prioritários: locação/comodato/aluguel de equipamentos analíticos (hematologia, bioquímica, coagulação, imunologia, ionograma, gasometria/POCT), reagentes/insumos laboratoriais, consumíveis (luvas, máscaras, tubos/coleta). É o primeiro corte para reduzir ruído.
- Positivos padrão: termos da área laboratório/hospitalar (reagentes, equipamentos, manutenção preventiva, linhas analíticas).
- Negativos padrão: planos de saúde, serviços puros, obras/engenharia, viagens, combustíveis, veículos, TI genérica, odontológico, merenda, materiais de construção etc.
- Apenas editais com prazo de proposta aberto: data de encerramento >= hoje (ou sem data, no caso de diários/PDF).
- Ordenação/score: peso alto para match de catálogo (fuzzy), peso menor para termos padrão e urgência de prazo; alertas via WhatsApp para scores altos ou match de produto.

## Uso rápido
1) Criar venv: `python3 -m venv .venv && source .venv/bin/activate`
2) Instalar deps: `pip install -r requirements.txt`
3) Rodar app: `streamlit run dashboard.py`
4) Preencher catálogo em “Meu Catálogo” (nome + palavras-chave por produto).
5) Em “Buscar Licitações”, rodar PNCP (modo padrão busca apenas prazos abertos) e opcionalmente os diários (FEMURN/FAMUP/AMUPE/AL).
6) Alertas: configure WhatsApp em “Configurações” (CallMeBot) para receber mensagens automáticas quando surgir licitação aderente.

## Observações
- Se um edital específico não aparecer, confirme que o prazo está aberto e a data de publicação está dentro da janela (padrão 60 dias). Você pode reprocessar após limpar o histórico ou ajustar a janela na busca.
- Scrapers externos (PDF) usam os mesmos termos para reduzir ruído; avisos sem data são mantidos para evitar perda. 
