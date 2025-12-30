"""
FastAPI Backend para o Sistema de Licitações
Expõe endpoints REST para acesso externo
"""
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configuração FastAPI
app = FastAPI(
    title="Medcal Licitações API",
    description="API REST para gerenciamento de licitações e catálogo de produtos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - Permite acesso de qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === MODELOS PYDANTIC ===

class LicitacaoBase(BaseModel):
    orgao: str
    uf: str
    modalidade: Optional[str] = None
    objeto: Optional[str] = None
    link: Optional[str] = None
    data_sessao: Optional[datetime] = None
    status: Optional[str] = "Nova"

class LicitacaoResponse(LicitacaoBase):
    id: int
    pncp_id: Optional[str] = None
    fonte: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    num_itens: int = 0
    score_relevancia: Optional[float] = None
    
    class Config:
        from_attributes = True

class ProdutoBase(BaseModel):
    nome: str
    palavras_chave: Optional[str] = None
    preco_custo: float = 0.0
    margem_minima: float = 0.0

class ProdutoResponse(ProdutoBase):
    id: int
    
    class Config:
        from_attributes = True

class BuscaRequest(BaseModel):
    dias: int = 30
    estados: List[str] = ["RN", "PB", "PE", "AL"]
    fontes: Optional[List[str]] = None

class BuscaResponse(BaseModel):
    sucesso: bool
    mensagem: str
    total_encontrado: int = 0


# === ROUTERS ===

from api.routers import licitacoes, produtos

app.include_router(licitacoes.router, prefix="/licitacoes", tags=["Licitações"])
app.include_router(produtos.router, prefix="/produtos", tags=["Produtos"])


# === ENDPOINTS RAIZ ===

@app.get("/")
async def root():
    """Endpoint raiz - Status da API"""
    return {
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check para monitoramento"""
    return {"status": "healthy"}


# === EXECUÇÃO ===

def start_api():
    """Inicia o servidor FastAPI"""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start_api()
