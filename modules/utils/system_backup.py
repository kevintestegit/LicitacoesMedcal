"""
Utilitário de Backup/Restore do Sistema Completo.
Exporta e importa todos os dados em um único arquivo ZIP.
"""
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional


class SystemBackup:
    """
    Gerencia backup e restore completo do sistema.
    Inclui todos os bancos de dados e arquivos de configuração.
    """
    
    # Arquivos que fazem parte do backup
    FILES_TO_BACKUP = [
        "data/medcal.db",
        "data/financeiro.db", 
        "data/financeiro_historico.db",
        "data/catalogo_produtos.json",
        "data/whatsapp_notifications_sent.json",
        "data/distance_cache.json",
        "data/embeddings_cache.json",
    ]
    
    def __init__(self, base_dir: str = None):
        """
        Inicializa o gerenciador de backup.
        
        Args:
            base_dir: Diretório base do projeto. Default: detecta automaticamente.
        """
        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent.parent
        else:
            self.base_dir = Path(base_dir)
        
        self.backup_dir = self.base_dir / "backups" / "system"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def export_backup(self, description: str = "") -> dict:
        """
        Exporta todos os dados do sistema em um arquivo ZIP.
        
        Args:
            description: Descrição opcional do backup
            
        Returns:
            dict com sucesso, caminho do arquivo, e metadados
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"medcal_backup_{timestamp}.zip"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Força checkpoint dos bancos SQLite (WAL mode)
            self._checkpoint_databases()
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                files_included = []
                
                for file_rel in self.FILES_TO_BACKUP:
                    file_path = self.base_dir / file_rel
                    
                    if file_path.exists():
                        # Adiciona ao ZIP com caminho relativo
                        zipf.write(file_path, file_rel)
                        files_included.append(file_rel)
                        
                        # Para arquivos .db, também incluir -wal e -shm se existirem
                        if file_rel.endswith('.db'):
                            for suffix in ['-wal', '-shm']:
                                extra = file_path.parent / (file_path.name + suffix)
                                if extra.exists():
                                    zipf.write(extra, file_rel + suffix)
                
                # Adiciona metadados
                metadata = {
                    "timestamp": timestamp,
                    "datetime": datetime.now().isoformat(),
                    "description": description,
                    "files": files_included,
                    "version": "1.0"
                }
                zipf.writestr("backup_metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))
            
            # Calcula tamanho
            size_mb = round(backup_path.stat().st_size / (1024 * 1024), 2)
            
            return {
                "sucesso": True,
                "arquivo": str(backup_path),
                "nome": backup_name,
                "tamanho_mb": size_mb,
                "arquivos_incluidos": files_included,
                "timestamp": timestamp
            }
            
        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e)
            }
    
    def import_backup(self, zip_path: str, overwrite: bool = True) -> dict:
        """
        Importa um backup ZIP, substituindo os dados atuais.
        
        Args:
            zip_path: Caminho para o arquivo ZIP de backup
            overwrite: Se True, sobrescreve arquivos existentes
            
        Returns:
            dict com sucesso e detalhes
        """
        try:
            zip_path = Path(zip_path)
            
            if not zip_path.exists():
                return {"sucesso": False, "erro": "Arquivo não encontrado"}
            
            if not zipfile.is_zipfile(zip_path):
                return {"sucesso": False, "erro": "Arquivo não é um ZIP válido"}
            
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Verifica se tem metadados
                if "backup_metadata.json" not in zipf.namelist():
                    return {"sucesso": False, "erro": "Arquivo não é um backup válido do Medcal (sem metadados)"}
                
                # Lê metadados
                metadata = json.loads(zipf.read("backup_metadata.json").decode('utf-8'))
                
                # Extrai arquivos
                files_restored = []
                for file_name in zipf.namelist():
                    if file_name == "backup_metadata.json":
                        continue
                    
                    target_path = self.base_dir / file_name
                    
                    # Cria diretório se necessário
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Extrai arquivo
                    with zipf.open(file_name) as src, open(target_path, 'wb') as dst:
                        dst.write(src.read())
                    
                    files_restored.append(file_name)
            
            return {
                "sucesso": True,
                "arquivos_restaurados": files_restored,
                "metadata_backup": metadata
            }
            
        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e)
            }
    
    def list_backups(self) -> list:
        """Lista todos os backups disponíveis."""
        backups = []
        
        for zip_file in sorted(self.backup_dir.glob("medcal_backup_*.zip"), reverse=True):
            try:
                with zipfile.ZipFile(zip_file, 'r') as zipf:
                    if "backup_metadata.json" in zipf.namelist():
                        metadata = json.loads(zipf.read("backup_metadata.json").decode('utf-8'))
                        metadata["arquivo"] = str(zip_file)
                        metadata["nome"] = zip_file.name
                        metadata["tamanho_mb"] = round(zip_file.stat().st_size / (1024 * 1024), 2)
                        backups.append(metadata)
            except Exception:
                # Ignora arquivos corrompidos
                pass
        
        return backups
    
    def get_backup_bytes(self, backup_name: str) -> Optional[bytes]:
        """
        Retorna os bytes de um backup para download.
        
        Args:
            backup_name: Nome do arquivo de backup
            
        Returns:
            bytes do arquivo ou None
        """
        backup_path = self.backup_dir / backup_name
        
        if backup_path.exists():
            return backup_path.read_bytes()
        return None
    
    def _checkpoint_databases(self):
        """Força checkpoint dos bancos SQLite (WAL mode) para garantir dados atualizados."""
        import sqlite3
        
        for db_rel in self.FILES_TO_BACKUP:
            if db_rel.endswith('.db'):
                db_path = self.base_dir / db_rel
                if db_path.exists():
                    try:
                        conn = sqlite3.connect(str(db_path))
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                        conn.close()
                    except Exception:
                        pass  # Ignora erros de checkpoint


# Instância global
system_backup = SystemBackup()
