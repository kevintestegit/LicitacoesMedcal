import sys
import os
import time
import logging
from datetime import datetime

# Garante que o diretório raiz esteja no PATH para importar modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.core.search_engine import SearchEngine

# Configuração de Logs
logging.basicConfig(
    filename='autorun_service.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def logger_callback(msg):
    """Callback para imprimir no console e salvar no log"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")
    logging.info(msg)

def main():
    print("\n" + "="*60)
    print("🚀 [AUTORUN] Serviço de Monitoramento de Licitações (Medcal)")
    print("="*60 + "\n")
    
    try:
        engine = SearchEngine()
    except Exception as e:
        print(f"Erro ao inicializar Engine: {e}")
        return

    while True:
        try:
            logger_callback("--- Iniciando Nova Varredura Automática ---")
            
            # Executa a busca completa (PNCP + Externos)
            novos = engine.execute_full_search(dias=60, callback=logger_callback)
            
            logger_callback(f"--- Fim da Execução. {novos} novas licitações importadas. ---")
            logger_callback("Dormindo por 4 horas...")
            
        except KeyboardInterrupt:
            print("\nParando serviço...")
            break
        except Exception as e:
            logger_callback(f"CRITICAL ERROR: {e}")
            time.sleep(60) # Espera 1 min antes de tentar de novo em caso de erro
            continue
        
        # Espera 4 horas (14400 segundos)
        # Pode ser ajustado conforme necessidade
        time.sleep(14400)

if __name__ == "__main__":
    main()