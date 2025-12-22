"""
Módulo de Análise Profunda de Licitações
Realiza Deep Scan completo de editais fixados,
extraindo itens, impedimentos, requisitos e preparando para competição.
"""
import json
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

from modules.database.database import get_session, Licitacao, ItemLicitacao, Produto, Configuracao
from modules.scrapers.pncp_client import PNCPClient
from modules.scrapers.pdf_extractor import PDFExtractor
from modules.ai.ai_config import get_model


@dataclass
class DeepAnalysisResult:
    """Resultado da análise profunda de uma licitação"""
    licitacao_id: int
    analyzed_at: str
    
    # Resumo Executivo
    resumo_objeto: str
    valor_total_estimado: float
    prazo_entrega: str
    local_entrega: str
    
    # Itens Detalhados
    itens: List[Dict]
    total_itens: int
    itens_compativeis: int
    
    # Análise de Viabilidade
    score_viabilidade: int  # 0-100
    justificativa: str
    
    # Impedimentos e Requisitos
    impedimentos: List[str]  # Ex: "Exige atestado de capacidade técnica"
    requisitos_habilitacao: List[str]
    documentos_necessarios: List[str]
    
    # Análise de Competitividade
    pontos_fortes: List[str]
    pontos_fracos: List[str]
    riscos: List[str]
    
    # Recomendações
    recomendacao_final: str  # "PARTICIPAR", "ANALISAR", "DESCARTAR"
    proximos_passos: List[str]
    
    # Metadados
    pdf_analisados: List[str]
    texto_extraido_chars: int


class DeepAnalyzer:
    """Realiza análise profunda de licitações"""
    
    def __init__(self):
        self.client = PNCPClient()
        self.pdf_extractor = PDFExtractor()
        self.model = None
        try:
            self.model = get_model(temperature=0.1)
        except Exception:
            self.model = None
    
    def analyze(self, licitacao_id: int, force_refresh: bool = False) -> Optional[DeepAnalysisResult]:
        """
        Realiza análise profunda de uma licitação.
        
        Args:
            licitacao_id: ID da licitação no banco
            force_refresh: Se True, refaz análise mesmo se já existir
            
        Returns:
            DeepAnalysisResult com todos os dados ou None se falhar
        """
        session = get_session()
        
        try:
            lic = session.query(Licitacao).get(licitacao_id)
            if not lic:
                return None
            
            # Verifica se já tem análise salva (no campo comentarios como JSON)
            if not force_refresh and lic.comentarios:
                try:
                    cached = json.loads(lic.comentarios)
                    if cached.get('deep_analysis'):
                        return DeepAnalysisResult(**cached['deep_analysis'])
                except:
                    pass
            
            # 1. Coleta todos os PDFs do edital
            texto_completo = ""
            pdfs_analisados = []
            
            if lic.pncp_id and '-' in lic.pncp_id:
                parts = lic.pncp_id.split('-')
                if len(parts) >= 3:
                    lic_dict = {"cnpj": parts[0], "ano": parts[1], "seq": parts[2]}
                    arquivos = self.client.buscar_arquivos(lic_dict)
                    
                    for arq in arquivos:
                        url = arq.get('url', '')
                        nome = arq.get('titulo') or arq.get('nome') or 'arquivo'
                        
                        if url.lower().endswith('.pdf'):
                            try:
                                pdf_content = self.client.download_arquivo(url)
                                if pdf_content:
                                    texto = self.pdf_extractor.extract_text(pdf_content)
                                    if texto:
                                        texto_completo += f"\n\n=== {nome} ===\n{texto}"
                                        pdfs_analisados.append(nome)
                            except Exception as e:
                                print(f"Erro ao baixar {nome}: {e}")
            
            # 2. Busca itens da API (se ainda não tiver)
            itens_db = list(lic.itens)
            if not itens_db:
                if lic.pncp_id and '-' in lic.pncp_id:
                    parts = lic.pncp_id.split('-')
                    lic_dict = {"cnpj": parts[0], "ano": parts[1], "seq": parts[2]}
                    itens_api = self.client.buscar_itens(lic_dict)
                    
                    for i in itens_api:
                        item = ItemLicitacao(
                            licitacao_id=lic.id,
                            numero_item=i.get('numero') or 0,
                            descricao=i.get('descricao', ''),
                            quantidade=i.get('quantidade') or 0,
                            unidade=i.get('unidade', 'UN'),
                            valor_estimado=i.get('valor_estimado') or 0,
                            valor_unitario=i.get('valor_unitario') or 0
                        )
                        session.add(item)
                    session.commit()
                    itens_db = list(lic.itens)
            
            # 3. Se texto do PDF vazio, usa IA para extrair itens do PDF
            if not itens_db and texto_completo:
                itens_extraidos = self.pdf_extractor.extract_financial_data(texto_completo)
                if itens_extraidos:
                    for i in itens_extraidos:
                        item = ItemLicitacao(
                            licitacao_id=lic.id,
                            numero_item=i.get('numero') or 0,
                            descricao=i.get('descricao', ''),
                            quantidade=i.get('quantidade') or 0,
                            unidade=i.get('unidade', 'UN'),
                            valor_estimado=i.get('valor_estimado') or 0,
                            valor_unitario=i.get('valor_unitario') or 0
                        )
                        session.add(item)
                    session.commit()
                    itens_db = list(lic.itens)
            
            # 4. Monta contexto para IA
            itens_texto = "\n".join([
                f"Item {i.numero_item}: {i.descricao} | Qtd: {i.quantidade} {i.unidade} | Valor Unit: R$ {i.valor_unitario or 0:.2f}"
                for i in itens_db
            ]) if itens_db else "Nenhum item detalhado encontrado."
            
            # Busca produtos do catálogo para comparação
            produtos = session.query(Produto).all()
            catalogo_texto = "\n".join([
                f"- {p.nome}: {p.palavras_chave}"
                for p in produtos
            ]) if produtos else "Catálogo vazio."
            
            # 5. Análise com IA
            if not self.model:
                return self._create_basic_result(lic, itens_db, pdfs_analisados, len(texto_completo))
            
            prompt = f"""
Você é um Especialista em Licitações Públicas para a empresa MEDCAL FARMA.
A Medcal fornece equipamentos laboratoriais (hematologia, bioquímica, coagulação, imunologia, ionograma, gasometria) em regime de locação/comodato com fornecimento de reagentes e insumos.

ANALISE A SEGUINTE LICITAÇÃO:

ÓRGÃO: {lic.orgao}
UF: {lic.uf}
MODALIDADE: {lic.modalidade}
OBJETO: {lic.objeto}
DATA ENCERRAMENTO: {lic.data_encerramento_proposta}

ITENS DA LICITAÇÃO:
{itens_texto}

MEU CATÁLOGO DE PRODUTOS:
{catalogo_texto}

TEXTO EXTRAÍDO DOS ANEXOS (Edital/Termo de Referência):
{texto_completo[:80000]}

TAREFA: Analise profundamente e retorne um JSON com a seguinte estrutura:
{{
    "resumo_objeto": "Resumo claro do que está sendo licitado",
    "valor_total_estimado": 0.0,
    "prazo_entrega": "Ex: 30 dias após assinatura",
    "local_entrega": "Cidade/Estado",
    
    "itens_compativeis": 0,
    "score_viabilidade": 0,
    "justificativa": "Por que esse score?",
    
    "impedimentos": ["Lista de impedimentos que podem nos excluir"],
    "requisitos_habilitacao": ["Documentos/requisitos para habilitação"],
    "documentos_necessarios": ["Lista de documentos a preparar"],
    
    "pontos_fortes": ["Vantagens competitivas da Medcal"],
    "pontos_fracos": ["Desvantagens ou dificuldades"],
    "riscos": ["Riscos identificados"],
    
    "recomendacao_final": "PARTICIPAR ou ANALISAR ou DESCARTAR",
    "proximos_passos": ["Lista ordenada de ações a tomar"]
}}

REGRAS:
- score_viabilidade: 0-100 (100=perfeito para Medcal)
- Se houver exigência de marca específica ou fornecedor único, é impedimento grave
- Se exigir atestado de capacidade técnica muito alto, considere risco
- Analise valores de referência vs nossos custos (se disponível)
- Seja REALISTA e DIRETO nas recomendações

Retorne APENAS o JSON, sem explicações adicionais.
"""
            
            try:
                response = self.model.generate_content(prompt)
                raw_text = response.text.strip()
                
                # Limpa markdown
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                
                analysis = json.loads(raw_text)
                
            except Exception as e:
                print(f"Erro na análise IA: {e}")
                return self._create_basic_result(lic, itens_db, pdfs_analisados, len(texto_completo))
            
            # 6. Monta resultado
            result = DeepAnalysisResult(
                licitacao_id=licitacao_id,
                analyzed_at=datetime.now().isoformat(),
                
                resumo_objeto=analysis.get('resumo_objeto', lic.objeto),
                valor_total_estimado=analysis.get('valor_total_estimado', 0),
                prazo_entrega=analysis.get('prazo_entrega', 'Não informado'),
                local_entrega=analysis.get('local_entrega', lic.uf),
                
                itens=[{"numero": i.numero_item, "descricao": i.descricao, "quantidade": i.quantidade} for i in itens_db],
                total_itens=len(itens_db),
                itens_compativeis=analysis.get('itens_compativeis', 0),
                
                score_viabilidade=analysis.get('score_viabilidade', 50),
                justificativa=analysis.get('justificativa', ''),
                
                impedimentos=analysis.get('impedimentos', []),
                requisitos_habilitacao=analysis.get('requisitos_habilitacao', []),
                documentos_necessarios=analysis.get('documentos_necessarios', []),
                
                pontos_fortes=analysis.get('pontos_fortes', []),
                pontos_fracos=analysis.get('pontos_fracos', []),
                riscos=analysis.get('riscos', []),
                
                recomendacao_final=analysis.get('recomendacao_final', 'ANALISAR'),
                proximos_passos=analysis.get('proximos_passos', []),
                
                pdf_analisados=pdfs_analisados,
                texto_extraido_chars=len(texto_completo)
            )
            
            # 7. Salva no banco
            lic.comentarios = json.dumps({
                'deep_analysis': asdict(result),
                'updated_at': datetime.now().isoformat()
            })
            session.commit()
            
            return result
            
        except Exception as e:
            print(f"Erro na análise profunda: {e}")
            return None
        finally:
            session.close()
    
    def _create_basic_result(self, lic, itens_db, pdfs, texto_len) -> DeepAnalysisResult:
        """Cria resultado básico quando IA não está disponível"""
        return DeepAnalysisResult(
            licitacao_id=lic.id,
            analyzed_at=datetime.now().isoformat(),
            
            resumo_objeto=lic.objeto,
            valor_total_estimado=sum(i.valor_estimado or 0 for i in itens_db),
            prazo_entrega="Ver edital",
            local_entrega=lic.uf,
            
            itens=[{"numero": i.numero_item, "descricao": i.descricao, "quantidade": i.quantidade} for i in itens_db],
            total_itens=len(itens_db),
            itens_compativeis=sum(1 for i in itens_db if i.produto_match_id),
            
            score_viabilidade=50,
            justificativa="Análise automática básica - IA não disponível",
            
            impedimentos=[],
            requisitos_habilitacao=["Ver edital para requisitos completos"],
            documentos_necessarios=["Documentos padrão de habilitação"],
            
            pontos_fortes=[],
            pontos_fracos=[],
            riscos=["Análise manual necessária"],
            
            recomendacao_final="ANALISAR",
            proximos_passos=["Ler edital completo", "Verificar requisitos", "Calcular proposta"],
            
            pdf_analisados=pdfs,
            texto_extraido_chars=texto_len
        )
    
    def get_cached_analysis(self, licitacao_id: int) -> Optional[DeepAnalysisResult]:
        """Retorna análise em cache sem refazer"""
        session = get_session()
        try:
            lic = session.query(Licitacao).get(licitacao_id)
            if lic and lic.comentarios:
                cached = json.loads(lic.comentarios)
                if cached.get('deep_analysis'):
                    return DeepAnalysisResult(**cached['deep_analysis'])
        except:
            pass
        finally:
            session.close()
        return None


# Instância global
deep_analyzer = DeepAnalyzer()
