"""
Router de Produtos - Endpoints REST para gerenciamento do catálogo de produtos
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# === MODELOS ===

class ProdutoBase(BaseModel):
    nome: str
    palavras_chave: Optional[str] = None
    preco_custo: float = 0.0
    margem_minima: float = 0.0
    preco_referencia: Optional[float] = None
    fonte_referencia: Optional[str] = None

class ProdutoCreate(ProdutoBase):
    pass

class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    palavras_chave: Optional[str] = None
    preco_custo: Optional[float] = None
    margem_minima: Optional[float] = None
    preco_referencia: Optional[float] = None
    fonte_referencia: Optional[str] = None

class ProdutoResponse(ProdutoBase):
    id: int
    
    class Config:
        from_attributes = True

class ProdutoListResponse(BaseModel):
    total: int
    produtos: List[ProdutoResponse]


# === ENDPOINTS ===

@router.get("/", response_model=ProdutoListResponse)
async def listar_produtos(
    busca: Optional[str] = Query(None, description="Buscar por nome ou palavras-chave"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """Lista todos os produtos do catálogo"""
    from modules.database.database import get_session, Produto
    
    session = get_session()
    try:
        query = session.query(Produto)
        
        if busca:
            busca_termo = f"%{busca}%"
            query = query.filter(
                (Produto.nome.ilike(busca_termo)) |
                (Produto.palavras_chave.ilike(busca_termo))
            )
        
        total = query.count()
        produtos = query.offset(offset).limit(limit).all()
        
        result = [
            ProdutoResponse(
                id=p.id,
                nome=p.nome,
                palavras_chave=p.palavras_chave,
                preco_custo=p.preco_custo or 0.0,
                margem_minima=p.margem_minima or 0.0,
                preco_referencia=p.preco_referencia,
                fonte_referencia=p.fonte_referencia,
            )
            for p in produtos
        ]
        
        return ProdutoListResponse(total=total, produtos=result)
    finally:
        session.close()


@router.get("/{produto_id}", response_model=ProdutoResponse)
async def obter_produto(produto_id: int):
    """Obtém detalhes de um produto específico"""
    from modules.database.database import get_session, Produto
    
    session = get_session()
    try:
        produto = session.query(Produto).filter(Produto.id == produto_id).first()
        
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        return ProdutoResponse(
            id=produto.id,
            nome=produto.nome,
            palavras_chave=produto.palavras_chave,
            preco_custo=produto.preco_custo or 0.0,
            margem_minima=produto.margem_minima or 0.0,
            preco_referencia=produto.preco_referencia,
            fonte_referencia=produto.fonte_referencia,
        )
    finally:
        session.close()


@router.post("/", response_model=ProdutoResponse)
async def criar_produto(produto: ProdutoCreate):
    """Cria um novo produto no catálogo"""
    from modules.database.database import get_session, Produto
    
    session = get_session()
    try:
        novo_produto = Produto(
            nome=produto.nome,
            palavras_chave=produto.palavras_chave,
            preco_custo=produto.preco_custo,
            margem_minima=produto.margem_minima,
            preco_referencia=produto.preco_referencia,
            fonte_referencia=produto.fonte_referencia,
        )
        
        session.add(novo_produto)
        session.commit()
        
        return ProdutoResponse(
            id=novo_produto.id,
            nome=novo_produto.nome,
            palavras_chave=novo_produto.palavras_chave,
            preco_custo=novo_produto.preco_custo or 0.0,
            margem_minima=novo_produto.margem_minima or 0.0,
            preco_referencia=novo_produto.preco_referencia,
            fonte_referencia=novo_produto.fonte_referencia,
        )
    finally:
        session.close()


@router.put("/{produto_id}", response_model=ProdutoResponse)
async def atualizar_produto(produto_id: int, data: ProdutoUpdate):
    """Atualiza um produto existente"""
    from modules.database.database import get_session, Produto
    
    session = get_session()
    try:
        produto = session.query(Produto).filter(Produto.id == produto_id).first()
        
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        # Atualiza apenas campos fornecidos
        if data.nome is not None:
            produto.nome = data.nome
        if data.palavras_chave is not None:
            produto.palavras_chave = data.palavras_chave
        if data.preco_custo is not None:
            produto.preco_custo = data.preco_custo
        if data.margem_minima is not None:
            produto.margem_minima = data.margem_minima
        if data.preco_referencia is not None:
            produto.preco_referencia = data.preco_referencia
        if data.fonte_referencia is not None:
            produto.fonte_referencia = data.fonte_referencia
        
        session.commit()
        
        return ProdutoResponse(
            id=produto.id,
            nome=produto.nome,
            palavras_chave=produto.palavras_chave,
            preco_custo=produto.preco_custo or 0.0,
            margem_minima=produto.margem_minima or 0.0,
            preco_referencia=produto.preco_referencia,
            fonte_referencia=produto.fonte_referencia,
        )
    finally:
        session.close()


@router.delete("/{produto_id}")
async def deletar_produto(produto_id: int):
    """Remove um produto do catálogo"""
    from modules.database.database import get_session, Produto
    
    session = get_session()
    try:
        produto = session.query(Produto).filter(Produto.id == produto_id).first()
        
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        session.delete(produto)
        session.commit()
        
        return {"sucesso": True, "mensagem": f"Produto '{produto.nome}' removido"}
    finally:
        session.close()
