"""
Sistema de Backup Automático para Dados Financeiros
- Backup diário/semanal automático
- Versionamento de dados
- Restauração simplificada
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import List, Dict, Optional
import threading
import time


class BackupManager:
    """Gerenciador de backups automáticos do banco financeiro"""

    def __init__(self, db_path: str = None, backup_dir: str = "backups/finance"):
        # Detecta automaticamente o caminho do banco se não for fornecido
        if db_path is None:
            base_dir = Path(__file__).parent.parent.parent
            self.db_path = str(base_dir / 'data' / 'financeiro.db')
        else:
            self.db_path = db_path

        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Arquivo de configuração de backups
        self.config_file = self.backup_dir / "backup_config.json"
        self.config = self._load_config()

        # Thread de backup automático
        self.backup_thread = None
        self.running = False

    def _load_config(self) -> Dict:
        """Carrega configurações de backup"""
        default_config = {
            "enabled": False,
            "frequency": "daily",  # daily, weekly
            "hour": 2,  # Hora do dia para fazer backup (2h da manhã)
            "keep_last": 30,  # Manter últimos 30 backups
            "last_backup": None
        }

        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return {**default_config, **json.load(f)}
        return default_config

    def _save_config(self):
        """Salva configurações de backup"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def criar_backup(self, descricao: str = "Backup automático") -> Dict:
        """
        Cria um backup do banco de dados financeiro

        Returns:
            Dict com informações do backup criado
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"finance_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_filename

        try:
            # Copia o arquivo do banco de dados
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"Banco de dados não encontrado: {self.db_path}")

            shutil.copy2(self.db_path, backup_path)

            # Cria arquivo de metadados
            metadata = {
                "timestamp": timestamp,
                "datetime": datetime.now().isoformat(),
                "descricao": descricao,
                "tamanho_bytes": backup_path.stat().st_size,
                "tamanho_mb": round(backup_path.stat().st_size / (1024 * 1024), 2),
                "arquivo": backup_filename
            }

            metadata_file = self.backup_dir / f"finance_backup_{timestamp}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Atualiza configuração
            self.config["last_backup"] = datetime.now().isoformat()
            self._save_config()

            # Limpa backups antigos
            self._limpar_backups_antigos()

            return {
                "sucesso": True,
                "arquivo": str(backup_path),
                "metadata": metadata
            }

        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e)
            }

    def listar_backups(self) -> List[Dict]:
        """Lista todos os backups disponíveis"""
        backups = []

        for metadata_file in sorted(self.backup_dir.glob("finance_backup_*.json"), reverse=True):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                # Verifica se o arquivo de backup existe
                backup_file = self.backup_dir / metadata["arquivo"]
                if backup_file.exists():
                    backups.append(metadata)
            except:
                continue

        return backups

    def restaurar_backup(self, timestamp: str) -> Dict:
        """
        Restaura um backup específico

        Args:
            timestamp: Timestamp do backup a restaurar (formato: YYYYMMDD_HHMMSS)

        Returns:
            Dict com resultado da operação
        """
        backup_file = self.backup_dir / f"finance_backup_{timestamp}.db"

        if not backup_file.exists():
            return {
                "sucesso": False,
                "erro": "Backup não encontrado"
            }

        try:
            # Cria backup do estado atual antes de restaurar
            self.criar_backup(descricao="Backup antes de restauração")

            # Restaura o backup
            shutil.copy2(backup_file, self.db_path)

            return {
                "sucesso": True,
                "mensagem": f"Backup de {timestamp} restaurado com sucesso"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e)
            }

    def deletar_backup(self, timestamp: str) -> Dict:
        """Deleta um backup específico"""
        backup_file = self.backup_dir / f"finance_backup_{timestamp}.db"
        metadata_file = self.backup_dir / f"finance_backup_{timestamp}.json"

        try:
            if backup_file.exists():
                backup_file.unlink()
            if metadata_file.exists():
                metadata_file.unlink()

            return {
                "sucesso": True,
                "mensagem": "Backup deletado com sucesso"
            }
        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e)
            }

    def _limpar_backups_antigos(self):
        """Remove backups antigos mantendo apenas os últimos N"""
        backups = self.listar_backups()
        keep_last = self.config.get("keep_last", 30)

        if len(backups) > keep_last:
            for backup in backups[keep_last:]:
                self.deletar_backup(backup["timestamp"])

    def configurar_backup_automatico(self, enabled: bool, frequency: str = "daily",
                                    hour: int = 2, keep_last: int = 30):
        """
        Configura o backup automático

        Args:
            enabled: Ativa/desativa backup automático
            frequency: Frequência ('daily' ou 'weekly')
            hour: Hora do dia para executar (0-23)
            keep_last: Quantos backups manter
        """
        self.config["enabled"] = enabled
        self.config["frequency"] = frequency
        self.config["hour"] = hour
        self.config["keep_last"] = keep_last
        self._save_config()

        # Reinicia thread de backup se necessário
        if enabled and not self.running:
            self.iniciar_backup_automatico()
        elif not enabled and self.running:
            self.parar_backup_automatico()

    def iniciar_backup_automatico(self):
        """Inicia o serviço de backup automático em background"""
        if self.running:
            return

        self.running = True
        self.backup_thread = threading.Thread(target=self._backup_loop, daemon=True)
        self.backup_thread.start()

    def parar_backup_automatico(self):
        """Para o serviço de backup automático"""
        self.running = False
        if self.backup_thread:
            self.backup_thread.join(timeout=5)

    def _backup_loop(self):
        """Loop principal do backup automático"""
        while self.running:
            try:
                if self.config.get("enabled", False):
                    now = datetime.now()

                    # Verifica se deve fazer backup
                    should_backup = False
                    last_backup = self.config.get("last_backup")

                    if not last_backup:
                        should_backup = True
                    else:
                        last_backup_dt = datetime.fromisoformat(last_backup)

                        if self.config["frequency"] == "daily":
                            # Backup diário na hora configurada
                            if now.hour == self.config["hour"] and now.date() > last_backup_dt.date():
                                should_backup = True

                        elif self.config["frequency"] == "weekly":
                            # Backup semanal (domingo na hora configurada)
                            if (now.weekday() == 6 and  # Domingo
                                now.hour == self.config["hour"] and
                                (now - last_backup_dt).days >= 7):
                                should_backup = True

                    if should_backup:
                        self.criar_backup(descricao=f"Backup automático {self.config['frequency']}")

                # Aguarda 1 hora antes de verificar novamente
                time.sleep(3600)

            except Exception as e:
                print(f"Erro no backup automático: {e}")
                time.sleep(3600)

    def get_estatisticas(self) -> Dict:
        """Retorna estatísticas sobre os backups"""
        backups = self.listar_backups()

        if not backups:
            return {
                "total_backups": 0,
                "tamanho_total_mb": 0,
                "ultimo_backup": None
            }

        tamanho_total = sum(b.get("tamanho_mb", 0) for b in backups)

        return {
            "total_backups": len(backups),
            "tamanho_total_mb": round(tamanho_total, 2),
            "ultimo_backup": backups[0] if backups else None,
            "mais_antigo": backups[-1] if backups else None
        }
