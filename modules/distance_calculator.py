import json
import os
import time
import requests

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut
    _GEOPY_AVAILABLE = True
except ImportError:
    _GEOPY_AVAILABLE = False

# Caminho para o arquivo de cache
CACHE_FILE = os.path.join("data", "distance_cache.json")

# Carrega o cache existente ou cria um novo
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        distance_cache = json.load(f)
else:
    distance_cache = {}

def save_cache():
    """Salva o cache em disco."""
    # Garante que a pasta data existe
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(distance_cache, f, ensure_ascii=False, indent=4)

def get_coordinates(city_name):
    """
    Obtém (lat, lon) de uma cidade.
    Usa cache para evitar chamadas repetidas ao Nominatim.
    """
    if not _GEOPY_AVAILABLE:
        return None
    city_key = f"COORD_{city_name.lower().strip()}"
    
    if city_key in distance_cache:
        return distance_cache[city_key]

    geolocator = Nominatim(user_agent="licitacoes_medcal_system_v1")
    try:
        # Adiciona ", Brasil" para melhorar a precisão
        location = geolocator.geocode(f"{city_name}, Brasil", timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            distance_cache[city_key] = coords
            save_cache()
            time.sleep(1) # Respeita o limite da API gratuita (1 req/s)
            return coords
    except (GeocoderTimedOut, Exception) as e:
        print(f"Erro ao geocodificar {city_name}: {e}")
    
    return None

def get_road_distance(origin, destination):
    """
    Calcula a distância rodoviária (de carro) em KM entre duas cidades.
    Usa a API OSRM (Open Source Routing Machine).
    """
    # Chave única para o par de cidades
    route_key = f"ROUTE_{origin.lower().strip()}_{destination.lower().strip()}"
    
    # 1. Verifica se já temos essa distância no cache
    if route_key in distance_cache:
        return distance_cache[route_key]

    # 2. Obtém coordenadas
    coords_origin = get_coordinates(origin)
    coords_dest = get_coordinates(destination)

    if not coords_origin or not coords_dest:
        return None

    # 3. Consulta a API OSRM
    # Formato: {lon},{lat};{lon},{lat}
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_origin[1]},{coords_origin[0]};{coords_dest[1]},{coords_dest[0]}"
    params = {"overview": "false"} # Não precisamos da geometria da rota, só a distância

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("routes"):
                # A distância vem em metros, convertemos para KM
                distance_meters = data["routes"][0]["distance"]
                distance_km = round(distance_meters / 1000, 2)
                
                # Salva no cache
                distance_cache[route_key] = distance_km
                save_cache()
                
                return distance_km
    except Exception as e:
        print(f"Erro na API OSRM: {e}")

    return None

# --- Bloco de Teste ---
if __name__ == "__main__":
    # Teste rápido
    origem = "Natal - RN"
    destinos = ["Piancó - PB", "João Pessoa - PB", "Recife - PE"]
    
    print(f"Calculando distâncias a partir de {origem}...\n")
    
    for destino in destinos:
        km = get_road_distance(origem, destino)
        if km:
            custo = km * 1.0 # R$ 1,00 por KM
            print(f"📍 {destino}: {km} km (Rodoviário) -> Custo Ida: R$ {custo:.2f}")
        else:
            print(f"❌ {destino}: Não foi possível calcular.")
