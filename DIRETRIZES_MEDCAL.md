# Diretrizes de Negócio - Medcal

Este documento define o foco de atuação da Medcal e orienta a configuração dos filtros de busca e algoritmos de IA do sistema de licitações.

## O Que a Medcal Faz
A Medcal é uma fornecedora especializada em produtos para a área de saúde laboratorial e hospitalar.

### Foco Principal
*   **Equipamentos de Análises Clínicas:** Equipamentos biomédicos, analisadores automatizados (Bioquímica, Hematologia, Coagulação, etc.), analisadores de íons, gasometria, etc.
*   **Insumos Laboratoriais:** Reagentes, calibradores, controles, tubos de coleta, ponteiras, lâminas, etc.
*   **Insumos Hospitalares Gerais:** Luvas, máscaras, cateteres, sondas, equipos, seringas, agulhas.

### O Que a Medcal NÃO Faz
*   **Medicamentos:** A empresa **NÃO** fornece remédios ou fármacos de qualquer tipo.
*   **Odontologia:** A empresa **NÃO** trabalha com equipamentos ou insumos odontológicos (cadeiras, motores, resinas, etc.).
*   **Prestação de Serviços Puros:** A empresa não realiza exames, não faz limpeza, não faz segurança, não faz obras. (Exceção: locação de equipamentos com fornecimento de insumos, conhecido como comodato).

## Diretrizes para Configuração do Sistema

### 1. Filtros de Busca (PNCP/Scrapers)
*   **Termos Negativos (O que BLOQUEAR):**
    *   "MEDICAMENTOS" (exceto se for "Materiais Médicos", mas cuidado com ambiguidades).
    *   "ODONTOLÓGICO", "ODONTOLOGIA", "DENTÁRIO".
    *   "FARMÁCIA BÁSICA", "FARMÁCIA HOSPITALAR" (se focado apenas em remédios).
    *   "OBRAS", "ENGENHARIA", "LIMPEZA", "VIGILÂNCIA", "ALIMENTAÇÃO".
    *   "SERVIÇOS DE EXAMES" (nós vendemos o equipamento para fazer o exame, não o serviço do exame em si).

*   **Termos Positivos (O que BUSCAR):**
    *   "EQUIPAMENTOS LABORATORIAIS", "INSUMOS LABORATORIAIS".
    *   "ANALISADOR", "HEMATOLOGIA", "BIOQUÍMICA".
    *   "MATERIAL HOSPITALAR", "MATERIAL MÉDICO".
    *   "REAGENTES", "DIAGNÓSTICO".

### 2. Matching de IA
*   A IA deve ser capaz de distinguir entre **comprar um equipamento** e **contratar um serviço de exames**.
*   A IA deve diferenciar **Insumos** (tubos, reagentes) de **Medicamentos**.

---
*Atualizado em: 09/12/2025*
