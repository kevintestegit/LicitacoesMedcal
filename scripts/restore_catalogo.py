#!/usr/bin/env python3
"""
Script para restaurar o catálogo de produtos da Medcal.
Execute: python scripts/restore_catalogo.py
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database.database import get_session, Produto, init_db

def restaurar_catalogo():
    """Restaura o catálogo de produtos padrão da Medcal."""
    
    # Inicializa o banco
    init_db()
    session = get_session()
    
    # Catálogo base para Medcal - Equipamentos e Insumos de Laboratório
    produtos = [
        # Equipamentos de Hematologia
        {
            "nome": "Analisador Hematológico Automatizado",
            "palavras_chave": "HEMATOLOGIA, ANALISADOR HEMATOLOGICO, HEMOGRAMA, CBC, CONTADOR DE CELULAS, EQUIPAMENTO HEMATOLOGIA, LOCACAO HEMATOLOGIA",
            "preco_custo": 85000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Reagentes para Hematologia",
            "palavras_chave": "REAGENTE HEMATOLOGIA, DILUENTE, LISANTE, REAGENTES HEMATOLOGICOS, INSUMOS HEMATOLOGIA",
            "preco_custo": 1500.00,
            "margem_minima": 30.0
        },
        
        # Equipamentos de Bioquímica
        {
            "nome": "Analisador Bioquímico Automatizado",
            "palavras_chave": "BIOQUIMICA, ANALISADOR BIOQUIMICO, QUIMICA CLINICA, EQUIPAMENTO BIOQUIMICA, LOCACAO BIOQUIMICA, AUTOMACAO BIOQUIMICA",
            "preco_custo": 120000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Reagentes para Bioquímica",
            "palavras_chave": "REAGENTE BIOQUIMICA, GLICOSE, COLESTEROL, TRIGLICERIDES, UREIA, CREATININA, TGO, TGP, ENZIMAS, REAGENTES BIOQUIMICOS",
            "preco_custo": 2000.00,
            "margem_minima": 30.0
        },
        
        # Equipamentos de Coagulação
        {
            "nome": "Analisador de Coagulação",
            "palavras_chave": "COAGULACAO, ANALISADOR COAGULACAO, COAGULOMETRO, TP, TTPA, TT, FIBRINOGENIO, EQUIPAMENTO COAGULACAO, HEMOSTASIA",
            "preco_custo": 45000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Reagentes para Coagulação",
            "palavras_chave": "REAGENTE COAGULACAO, TROMBOPLASTINA, REAGENTES COAGULACAO, INSUMOS COAGULACAO, HEMOSTASIA",
            "preco_custo": 800.00,
            "margem_minima": 30.0
        },
        
        # Equipamentos de Imunologia
        {
            "nome": "Analisador de Imunologia/Hormônios",
            "palavras_chave": "IMUNOLOGIA, HORMONIOS, ANALISADOR IMUNOLOGIA, IMUNOENSAIO, ELISA, QUIMIOLUMINESCENCIA, EQUIPAMENTO IMUNOLOGIA, TSH, T4, T3",
            "preco_custo": 150000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Reagentes para Imunologia",
            "palavras_chave": "REAGENTE IMUNOLOGIA, HORMONIOS, TSH, T4 LIVRE, T3, PSA, BETA HCG, REAGENTES IMUNOLOGICOS",
            "preco_custo": 3500.00,
            "margem_minima": 30.0
        },
        
        # Equipamentos de Ionograma/Eletrólitos
        {
            "nome": "Analisador de Eletrólitos/Ionograma",
            "palavras_chave": "IONOGRAMA, ELETROLITOS, ANALISADOR IONS, SODIO, POTASSIO, CLORO, CALCIO IONICO, EQUIPAMENTO IONOGRAMA",
            "preco_custo": 35000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Reagentes para Ionograma",
            "palavras_chave": "REAGENTE IONOGRAMA, ELETROLITOS, SOLUCAO CALIBRADORA, REAGENTES IONOGRAMA",
            "preco_custo": 600.00,
            "margem_minima": 30.0
        },
        
        # Gasometria/POCT
        {
            "nome": "Analisador de Gasometria/POCT",
            "palavras_chave": "GASOMETRIA, POCT, POINT OF CARE, GASES SANGUINEOS, PH, PCO2, PO2, EQUIPAMENTO GASOMETRIA, HEMOGASOMETRO",
            "preco_custo": 55000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Cartuchos/Reagentes Gasometria",
            "palavras_chave": "CARTUCHO GASOMETRIA, REAGENTE GASOMETRIA, SENSOR GASOMETRIA, INSUMOS GASOMETRIA, POCT",
            "preco_custo": 1200.00,
            "margem_minima": 30.0
        },
        
        # Urinálise
        {
            "nome": "Analisador de Urina",
            "palavras_chave": "URANALISE, ANALISE URINA, ANALISADOR URINA, SUMARIO DE URINA, EAS, EQUIPAMENTO URINA",
            "preco_custo": 25000.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Tiras Reagentes para Urina",
            "palavras_chave": "TIRA REAGENTE URINA, FITA URINA, REAGENTE URINA, URANALISE",
            "preco_custo": 300.00,
            "margem_minima": 35.0
        },
        
        # Consumíveis Gerais
        {
            "nome": "Tubos para Coleta de Sangue",
            "palavras_chave": "TUBO COLETA, TUBO VACUO, TUBO EDTA, TUBO HEPARINA, TUBO CITRATO, TUBO GEL, COLETA SANGUE, TUBOS",
            "preco_custo": 0.80,
            "margem_minima": 40.0
        },
        {
            "nome": "Luvas de Procedimento",
            "palavras_chave": "LUVA, LUVAS, LUVA PROCEDIMENTO, LUVA LATEX, LUVA NITRILO, LUVA VINIL",
            "preco_custo": 25.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Máscaras Descartáveis",
            "palavras_chave": "MASCARA, MASCARAS, MASCARA CIRURGICA, MASCARA DESCARTAVEL, MASCARA TNT",
            "preco_custo": 15.00,
            "margem_minima": 35.0
        },
        
        # Testes Rápidos
        {
            "nome": "Testes Rápidos Diagnósticos",
            "palavras_chave": "TESTE RAPIDO, COVID, DENGUE, HIV, SIFILIS, HEPATITE, GRAVIDEZ, BETA HCG, IMUNOCROMATOGRAFIA",
            "preco_custo": 8.00,
            "margem_minima": 40.0
        },
        
        # Controles de Qualidade
        {
            "nome": "Controles de Qualidade Laboratorial",
            "palavras_chave": "CONTROLE QUALIDADE, CONTROLE INTERNO, CALIBRADOR, PADRAO, CONTROLE HEMATOLOGIA, CONTROLE BIOQUIMICA",
            "preco_custo": 500.00,
            "margem_minima": 30.0
        },
        
        # Manutenção
        {
            "nome": "Serviço de Manutenção Preventiva",
            "palavras_chave": "MANUTENCAO PREVENTIVA, MANUTENCAO EQUIPAMENTO, CALIBRACAO, AFERICAO, ASSISTENCIA TECNICA",
            "preco_custo": 2000.00,
            "margem_minima": 50.0
        },
        
        # Cateteres
        {
            "nome": "Cateter Intravenoso Periférico",
            "palavras_chave": "CATETER INTRAVENOSO, CATETER PERIFERICO, JELCO, ABOCATH, SCALP, CATETER VENOSO, ACESSO VENOSO PERIFERICO, CATETER IV",
            "preco_custo": 1.50,
            "margem_minima": 35.0
        },
        {
            "nome": "Cateter Venoso Central",
            "palavras_chave": "CATETER VENOSO CENTRAL, CVC, CATETER CENTRAL, ACESSO CENTRAL, DUPLO LUMEN, TRIPLO LUMEN, CATETER SUBCLAVIA, CATETER JUGULAR",
            "preco_custo": 85.00,
            "margem_minima": 30.0
        },
        {
            "nome": "Cateter Umbilical",
            "palavras_chave": "CATETER UMBILICAL, CATETER NEONATAL, CATETERIZACAO UMBILICAL, CATETER RN, CATETER ARTERIAL UMBILICAL, CATETER VENOSO UMBILICAL",
            "preco_custo": 35.00,
            "margem_minima": 30.0
        },
        {
            "nome": "Cateter para Oxigênio",
            "palavras_chave": "CATETER OXIGENIO, CATETER NASAL, CATETER O2, CATETER TIPO OCULOS, CANULA NASAL O2, PRONGAS NASAIS",
            "preco_custo": 2.50,
            "margem_minima": 35.0
        },
        {
            "nome": "Cateter para Hemodiálise",
            "palavras_chave": "CATETER HEMODIALISE, CATETER DIALISE, CATETER DUPLO LUMEN DIALISE, ACESSO VASCULAR DIALISE, CATETER PERMCATH, CATETER SHILEY",
            "preco_custo": 180.00,
            "margem_minima": 25.0
        },
        
        # Sondas
        {
            "nome": "Sonda Nasogástrica",
            "palavras_chave": "SONDA NASOGASTRICA, SONDA NG, SONDA LEVINE, SONDA GASTRICA, SONDA NASOGASTRICA LONGA, SNG",
            "preco_custo": 3.50,
            "margem_minima": 35.0
        },
        {
            "nome": "Sonda Nasoenteral",
            "palavras_chave": "SONDA NASOENTERAL, SONDA ENTERAL, SONDA SNE, SONDA DOBBHOFF, SONDA ALIMENTACAO, SONDA NUTRICAO ENTERAL",
            "preco_custo": 25.00,
            "margem_minima": 30.0
        },
        {
            "nome": "Sonda Vesical de Demora (Foley)",
            "palavras_chave": "SONDA FOLEY, SONDA VESICAL DEMORA, SVD, CATETER FOLEY, SONDA 2 VIAS, SONDA 3 VIAS, SONDA URETRAL DEMORA",
            "preco_custo": 8.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Sonda Vesical de Alívio",
            "palavras_chave": "SONDA ALIVIO, SONDA URETRAL, SONDA VESICAL ALIVIO, SVA, CATETERIZACAO ALIVIO, SONDA NELATON",
            "preco_custo": 2.00,
            "margem_minima": 40.0
        },
        {
            "nome": "Sonda Retal",
            "palavras_chave": "SONDA RETAL, SONDA EVACUADORA, SONDA GASES, TUBO RETAL, SONDA INTESTINAL",
            "preco_custo": 3.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Sonda Endotraqueal",
            "palavras_chave": "SONDA ENDOTRAQUEAL, TUBO ENDOTRAQUEAL, TOT, TUBO OROTRAQUEAL, INTUBACAO, TUBO TRAQUEAL, SONDA IOT",
            "preco_custo": 12.00,
            "margem_minima": 30.0
        },
        {
            "nome": "Sonda de Aspiração",
            "palavras_chave": "SONDA ASPIRACAO, SONDA ASPIRA, CATETER ASPIRACAO, SONDA TRAQUEAL, ASPIRACAO TRAQUEAL, SONDA SUCCAO",
            "preco_custo": 1.80,
            "margem_minima": 40.0
        },
        
        # Cânulas
        {
            "nome": "Cânula de Guedel",
            "palavras_chave": "CANULA GUEDEL, CANULA OROFARINGEA, AIRWAY, CANULA OROTRAQUEAL, CANULA ORAL, TUBO GUEDEL",
            "preco_custo": 4.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Cânula Nasofaríngea",
            "palavras_chave": "CANULA NASOFARINGEA, CANULA NASAL, AIRWAY NASAL, TUBO NASOFARINGEO, CANULA WENDL",
            "preco_custo": 6.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Cânula de Traqueostomia",
            "palavras_chave": "CANULA TRAQUEOSTOMIA, TUBO TRAQUEO, TRAQUEOSTOMO, TQT, CANULA TRAQUEAL, CANULA SHILEY, CANULA PORTEX",
            "preco_custo": 85.00,
            "margem_minima": 25.0
        },
        {
            "nome": "Cânula Nasal para Oxigênio",
            "palavras_chave": "CANULA NASAL, CATETER NASAL O2, OCULOS NASAL, CANULA OXIGENIO, PRONGAS NASAIS, CANULA TIPO OCULOS",
            "preco_custo": 2.00,
            "margem_minima": 40.0
        },
        {
            "nome": "Cânula de Alto Fluxo",
            "palavras_chave": "CANULA ALTO FLUXO, OXIGENOTERAPIA ALTO FLUXO, CNAF, HIGH FLOW, CATETER NASAL ALTO FLUXO, OPTIFLOW",
            "preco_custo": 45.00,
            "margem_minima": 30.0
        },
        
        # Equipos
        {
            "nome": "Equipo Macrogotas",
            "palavras_chave": "EQUIPO MACROGOTAS, EQUIPO SORO, EQUIPO SIMPLES, EQUIPO INFUSAO, EQUIPO MACROGOTA, EQUIPO GRAVITACIONAL",
            "preco_custo": 1.50,
            "margem_minima": 40.0
        },
        {
            "nome": "Equipo Microgotas",
            "palavras_chave": "EQUIPO MICROGOTAS, EQUIPO PEDIATRICO, EQUIPO MICROGOTA, EQUIPO PRECISAO, EQUIPO DOSADOR",
            "preco_custo": 2.50,
            "margem_minima": 40.0
        },
        {
            "nome": "Equipo Fotossensível",
            "palavras_chave": "EQUIPO FOTOSSENSIVEL, EQUIPO AMBAR, EQUIPO PROTEGIDO LUZ, EQUIPO FOTOSSENSIBILIDADE, EQUIPO ESCURO",
            "preco_custo": 4.50,
            "margem_minima": 35.0
        },
        {
            "nome": "Equipo com Bureta",
            "palavras_chave": "EQUIPO BURETA, EQUIPO GRADUADO, BURETA INFUSAO, EQUIPO VOLUMETRICO, BURETA 100ML, BURETA 150ML",
            "preco_custo": 8.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Equipo Multivias",
            "palavras_chave": "EQUIPO MULTIVIAS, EQUIPO DUPLA VIA, EQUIPO TRIPLA VIA, TORNEIRINHA, EQUIPO POLIVIAS, EXTENSOR MULTIVIAS",
            "preco_custo": 6.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Equipo para Bomba de Infusão",
            "palavras_chave": "EQUIPO BOMBA INFUSAO, EQUIPO BI, EQUIPO BOMBA, EQUIPO COMPATIVEL BOMBA, EQUIPO INFUSORA, SET BOMBA",
            "preco_custo": 12.00,
            "margem_minima": 30.0
        },
        {
            "nome": "Equipo para Nutrição Enteral",
            "palavras_chave": "EQUIPO ENTERAL, EQUIPO DIETA, EQUIPO NUTRICAO, EQUIPO ALIMENTACAO, EQUIPO SNE, SET ENTERAL",
            "preco_custo": 5.00,
            "margem_minima": 35.0
        },
        {
            "nome": "Equipo para Hemotransfusão",
            "palavras_chave": "EQUIPO HEMOTRANSFUSAO, EQUIPO SANGUE, EQUIPO TRANSFUSAO, EQUIPO HEMOCOMPONENTES, EQUIPO FILTRO SANGUE",
            "preco_custo": 8.00,
            "margem_minima": 30.0
        },
    ]
    
    # Pergunta se quer limpar ou adicionar
    produtos_existentes = session.query(Produto).count()
    
    if produtos_existentes > 0:
        print(f"⚠️  Existem {produtos_existentes} produtos no banco.")
        resposta = input("Deseja SUBSTITUIR todos? (s/N): ").strip().lower()
        if resposta == 's':
            session.query(Produto).delete()
            print("🗑️  Produtos anteriores removidos.")
        else:
            print("➕ Adicionando aos produtos existentes...")
    
    # Adiciona os produtos
    for p in produtos:
        produto = Produto(
            nome=p["nome"],
            palavras_chave=p["palavras_chave"],
            preco_custo=p["preco_custo"],
            margem_minima=p["margem_minima"],
            preco_referencia=0.0,
            fonte_referencia=""
        )
        session.add(produto)
    
    session.commit()
    
    # Confirma
    total = session.query(Produto).count()
    print(f"\n✅ Catálogo restaurado! Total de produtos: {total}")
    print("\nProdutos cadastrados:")
    for p in session.query(Produto).all():
        print(f"  • {p.nome}")
    
    session.close()

if __name__ == "__main__":
    print("=" * 50)
    print("🔄 RESTAURAÇÃO DO CATÁLOGO MEDCAL")
    print("=" * 50)
    print()
    restaurar_catalogo()
    print()
    print("=" * 50)
