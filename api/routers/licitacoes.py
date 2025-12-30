"""
Router de Licitações - Endpoints REST para gerenciamento de licitações
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

router = APIRouter()


# === MODELOS ===

class LicitacaoResponse(BaseModel):
    id: int
    pncp_id: Optional[str] = None
    orgao: str
    uf: str
    modalidade: Optional[str] = None
    objeto: Optional[str] = None
    link: Optional[str] = None
    fonte: Optional[str] = None
    status: Optional[str] = "Nova"
    data_sessao: Optional[datetime] = None
    data_publicacao: Optional[datetime] = None
    num_itens: int = 0
    has_matches: bool = False
    score_relevancia: Optional[float] = None
    
    class Config:
        from_attributes = True

class LicitacaoListResponse(BaseModel):
    total: int
    licitacoes: List[LicitacaoResponse]

class StatusUpdate(BaseModel):
    status: str


# === DEPENDÊNCIAS ===

def get_db_session():
    """Cria sessão do banco de dados"""
    from modules.database.database import get_session
    session = get_session()
    try:
        yield session
    finally:
        session.close()


# === ENDPOINTS ===

@router.get("/", response_model=LicitacaoListResponse)
async def listar_licitacoes(
    status: Optional[str] = Query(None, description="Filtrar por status: Nova, Salva, Analisada"),
    uf: Optional[str] = Query(None, description="Filtrar por UF"),
    fonte: Optional[str] = Query(None, description="Filtrar por fonte: PNCP, FEMURN, etc"),
    apenas_com_match: bool = Query(False, description="Apenas licitações com match de produtos"),
    limit: int = Query(100, le=500, description="Limite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginação"),
):
    """Lista licitações com filtros opcionais"""
    from modules.database.database import get_session, Licitacao
    
    session = get_session()
    try:
        query = session.query(Licitacao)
        
        if status:
            query = query.filter(Licitacao.status == status)
        if uf:
            query = query.filter(Licitacao.uf == uf.upper())
        if fonte:
            query = query.filter(Licitacao.fonte == fonte)
        
        # Total antes do limit
        total = query.count()
        
        # Ordenação e paginação
        licitacoes = query.order_by(Licitacao.data_publicacao.desc()).offset(offset).limit(limit).all()
        
        # Formata resposta
        result = []
        for lic in licitacoes:
            matches = sum(1 for item in lic.itens if item.produto_match_id is not None) if lic.itens else 0
            result.append(LicitacaoResponse(
                id=lic.id,
                pncp_id=lic.pncp_id,
                orgao=lic.orgao,
                uf=lic.uf,
                modalidade=lic.modalidade,
                objeto=lic.objeto,
                link=lic.link,
                fonte=lic.fonte,
                status=lic.status,
                data_sessao=lic.data_sessao,
                data_publicacao=lic.data_publicacao,
                num_itens=len(lic.itens) if lic.itens else 0,
                has_matches=matches > 0,
            ))
        
        if apenas_com_match:
            result = [r for r in result if r.has_matches]
            total = len(result)
        
        return LicitacaoListResponse(total=total, licitacoes=result)
    finally:
        session.close()


@router.get("/{licitacao_id}", response_model=LicitacaoResponse)
async def obter_licitacao(licitacao_id: int):
    """Obtém detalhes de uma licitação específica"""
    from modules.database.database import get_session, Licitacao
    
    session = get_session()
    try:
        lic = session.query(Licitacao).filter(Licitacao.id == licitacao_id).first()
        
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        
        matches = sum(1 for item in lic.itens if item.produto_match_id is not None) if lic.itens else 0
        
        return LicitacaoResponse(
            id=lic.id,
            pncp_id=lic.pncp_id,
            orgao=lic.orgao,
            uf=lic.uf,
            modalidade=lic.modalidade,
            objeto=lic.objeto,
            link=lic.link,
            fonte=lic.fonte,
            status=lic.status,
            data_sessao=lic.data_sessao,
            data_publicacao=lic.data_publicacao,
            num_itens=len(lic.itens) if lic.itens else 0,
            has_matches=matches > 0,
        )
    finally:
        session.close()


@router.patch("/{licitacao_id}/status")
async def atualizar_status(licitacao_id: int, data: StatusUpdate):
    """Atualiza o status de uma licitação"""
    from modules.database.database import get_session, Licitacao
    
    status_validos = ['Nova', 'Salva', 'Analisada', 'Descartada']
    if data.status not in status_validos:
        raise HTTPException(status_code=400, detail=f"Status inválido. Valores aceitos: {status_validos}")
    
    session = get_session()
    try:
        lic = session.query(Licitacao).filter(Licitacao.id == licitacao_id).first()
        
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        
        lic.status = data.status
        session.commit()
        
        return {"sucesso": True, "mensagem": f"Status atualizado para '{data.status}'"}
    finally:
        session.close()


@router.post("/buscar")
async def iniciar_busca(
    dias: int = Query(30, ge=1, le=90, description="Dias de histórico"),
    estados: str = Query("RN,PB,PE,AL", description="Estados separados por vírgula"),
):
    """Inicia uma busca por novas licitações"""
    from modules.core.background_search import background_manager
    
    estados_list = [e.strip().upper() for e in estados.split(",")]
    
    result = background_manager.start_search(dias=dias, estados=estados_list)
    
    if result.get("success"):
        return {"sucesso": True, "mensagem": result.get("message"), "run_id": result.get("run_id")}
    else:
        raise HTTPException(status_code=400, detail=result.get("message"))


@router.get("/busca/status")
async def status_busca():
    """Obtém o status da busca em andamento"""
    from modules.core.background_search import background_manager
    
    status = background_manager.get_current_status()
    return status


@router.get("/{licitacao_id}/relevancia")
async def calcular_relevancia(licitacao_id: int):
    """Calcula score de relevância usando ML"""
    from modules.database.database import get_session, Licitacao
    from modules.ml import LicitacaoClassifier
    
    session = get_session()
    try:
        lic = session.query(Licitacao).filter(Licitacao.id == licitacao_id).first()
        
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        
        classifier = LicitacaoClassifier()
        
        licitacao_dict = {
            'orgao': lic.orgao,
            'uf': lic.uf,
            'modalidade': lic.modalidade,
            'objeto': lic.objeto,
            'itens': [{'descricao': item.descricao} for item in lic.itens] if lic.itens else [],
        }
        
        score = classifier.predict_proba(licitacao_dict)
        
        return {
            "licitacao_id": licitacao_id,
            "score_relevancia": round(score, 3),
            "classificacao": "Relevante" if score >= 0.5 else "Não Relevante"
        }
    finally:
        session.close()
