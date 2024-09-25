import os
import requests
from serpapi import GoogleSearch
import json
import time

SERPAPI_KEY = "68ea65477e6d1364cb779432e97386315b6b6de331a2fcdb00580d2e5f00201e"

def download_images(local_result, output_dir):
    """
    :param local_result: Diccionario con la información del resultado local
    :param output_dir: Directorio donde se guardarán las imágenes
    """
    photos_link = local_result.get('photos_link')
    if not photos_link:
        print(f"No se encontró enlace de fotos para {local_result.get('title', 'resultado desconocido')}")
        return
    business_name = local_result.get('title', 'unknown').replace(' ', '_')
    business_dir = os.path.join(output_dir, business_name)
    os.makedirs(business_dir, exist_ok=True)

    photos_search = GoogleSearch({
        "api_key": SERPAPI_KEY,
        "engine": "google_maps_photos",
        "data_id": local_result['data_id'],
        "hl": "en"
    })
    photos_results = photos_search.get_dict()

    for i, photo in enumerate(photos_results.get('photos', [])):
        image_url = photo.get('image')
        if image_url:
            try:
                response = requests.get(image_url)
                if response.status_code == 200:
                    file_name = f"image_{i+1}.jpg"
                    file_path = os.path.join(business_dir, file_name)
                    with open(file_path, 'wb') as file:
                        file.write(response.content)
                    print(f"Imagen descargada: {file_path}")
                else:
                    print(f"Error al descargar la imagen {i+1}: Status code {response.status_code}")
            except Exception as e:
                print(f"Error al descargar la imagen {i+1}: {str(e)}")
        time.sleep(1)

def read_queries(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

def save_results(results, query, output_dir):
    filename = f"{query.replace(' ', '_')}.json"
    file_path = os.path.join(output_dir, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

def main():
    api_key = SERPAPI_KEY
    queries_file = "q.txt"   
    output_dir = "resultados" 
    os.makedirs(output_dir, exist_ok=True)

    queries = read_queries(queries_file)
    for query in queries:
        print(f"Procesando consulta: {query}")
        params = {
            "api_key": api_key,
            "engine": "google_maps",
            "type": "search",
            "google_domain": "google.com",
            "q": query,
            "hl": "en",
            "no_cache": "true"
        }
        try:
            search = GoogleSearch(params)
            results = search.get_dict()     
            save_results(results, query, output_dir)
            print(f"Resultados guardados para: {query}")
            for local_result in results.get('local_results', []):
                download_images(local_result, output_dir)
        except Exception as e:
            print(f"Error al procesar la consulta '{query}': {str(e)}")
        time.sleep(2)

    print("Proceso completado.")

if __name__ == "__main__":
    main()