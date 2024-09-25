from collections import defaultdict
from datetime import datetime
import shutil
import uuid
from celery import shared_task
from django.utils import timezone
from automation.consumers import get_log_file_path
from .models import BusinessImage, Destination, Review, ScrapingTask, Business, Category, OpeningHours, AdditionalInfo, Image
from django.conf import settings 
from serpapi import GoogleSearch
import json
import requests
from django.utils import timezone
import os
import logging
import asyncio
from .translation_utils import translate_business_info_sync
from serpapi import GoogleSearch
import time
from PIL import Image as PILImage
from io import BytesIO
from django.db import transaction
from django.core.management import call_command
from django.core.mail import send_mail
from django.db.models import Avg, Count
from django.db import connection
from django.template.loader import get_template
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
import psutil
from celery import shared_task
from celery.schedules import crontab
from celery import Celery
from django.core.files import File
from serpapi import GoogleSearch
from xhtml2pdf import pisa
from datetime import datetime
from tempfile import NamedTemporaryFile
from .celery import app
from django.core import management
from django.contrib.auth import get_user_model
from django.db import models
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import openai
import pycountry
from doctran import Doctran
from asgiref.sync import sync_to_async
import re
import unicodedata
import boto3
from botocore.exceptions import NoCredentialsError
#SERPAPI_KEY = settings.SERPAPI_KEY   
SERPAPI_KEY="c63b29e92a3a15f1974d4ca626d4f3ad5d752768608c5e2c8d96b03e2b2c7689"   #"68ea65477e6d1364cb779432e97386315b6b6de331a2fcdb00580d2e5f00201e"
OPENAI_API_KEY = openai.api_key = "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"


User = get_user_model()

logger = logging.getLogger(__name__)

doctran = Doctran(openai_api_key=OPENAI_API_KEY)


def process_scraping_task(task_id):
    log_file_path = get_log_file_path(task_id)
    file_handler = logging.FileHandler(log_file_path)
    logger.addHandler(file_handler)

    logger.info(f"Iniciando tarea de scraping {task_id}")
    task = ScrapingTask.objects.get(id=task_id)
    task.status = 'IN_PROGRESS'
    task.save()

    # Configurar el cliente de S3
    s3 = boto3.client('s3')
    bucket_name = 'nombre-de-tu-bucket'

    try:
        queries = read_queries(task.file.path)
        logger.info(f"Total de consultas a procesar: {len(queries)}")

        for query in queries:
            try:
                logger.info(f"Procesando consulta: {query}")
                params = {
                    "api_key": SERPAPI_KEY,
                    "engine": "google_maps",
                    "type": "search",
                    "google_domain": "google.com",
                    "q": query,
                    "hl": "en",
                    "no_cache": "true"
                }
                next_page_token = None
                page_num = 1
                total_results = 0
                max_pages = 7

                while page_num <= max_pages:
                    if next_page_token:
                        params["next_page_token"] = next_page_token
                    
                    search = GoogleSearch(params)
                    results = search.get_dict()

                    if 'error' in results:
                        logger.error(f"Error de API para la consulta '{query}' en la página {page_num}: {results['error']}")
                        break

                    save_results(task, results, query)

                    local_results = results.get('local_results', [])
                    for local_result in local_results:
                        business = save_business(task, local_result, query)
                        image_paths = download_images(business, local_result)
                        
                        # Subir imágenes a S3
                        for image_path in image_paths:
                            try:
                                s3_key = f"{task_id}/{business.id}/{os.path.basename(image_path)}"
                                s3.upload_file(image_path, bucket_name, s3_key)
                                logger.info(f"Imagen {image_path} subida exitosamente a S3 como {s3_key}")
                                 
                                s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
                                update_image_url(business, image_path, s3_url)
                                 
                                os.remove(image_path)
                            except NoCredentialsError:
                                logger.error("Credenciales de AWS no disponibles")
                            except Exception as e:
                                logger.error(f"Error al subir {image_path} a S3: {str(e)}")

                    total_results += len(local_results)
                    logger.info(f"Procesados {len(local_results)} resultados en la página {page_num} para la consulta '{query}'")

                    next_page_token = get_next_page_token(results)
                    if not next_page_token:
                        logger.info(f"No hay más páginas para la consulta '{query}'")
                        break

                    page_num += 1
                    time.sleep(2)
                logger.info(f"Total de resultados procesados para la consulta '{query}': {total_results}")

            except Exception as e:
                logger.error(f"Error al procesar la consulta '{query}': {str(e)}", exc_info=True)
                continue 

        logger.info(f"Tarea de scraping {task_id} completada con éxito")
        task.status = 'COMPLETED'
        task.completed_at = timezone.now()
        task.save()

    except Exception as e:
        logger.error(f"Error en la tarea de scraping {task_id}: {str(e)}", exc_info=True)
        task.status = 'FAILED'
        task.save()
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()
 
    cleanup_temp_files(task_id)
 
def cleanup_temp_files(task_id):
    """
    Elimina los archivos temporales asociados con una tarea específica.
    """
    temp_dir = os.path.join(settings.MEDIA_ROOT, f'temp_images_{task_id}')
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Directorio temporal para la tarea {task_id} eliminado: {temp_dir}")
        except Exception as e:
            logger.error(f"Error al eliminar el directorio temporal para la tarea {task_id}: {str(e)}")

def update_image_url(business, local_path, s3_url):
    """
    Actualiza la URL de la imagen en la base de datos con la URL de S3.
    """
    try:
        image = BusinessImage.objects.get(business=business, local_path=local_path)
        image.s3_url = s3_url
        image.local_path = ''  # Opcional: limpiar la ruta local si ya no es necesaria
        image.save()
        logger.info(f"URL de imagen actualizada para el negocio {business.id}: {s3_url}")
    except BusinessImage.DoesNotExist:
        logger.warning(f"No se encontró la imagen para el negocio {business.id} con ruta local {local_path}")
    except Exception as e:
        logger.error(f"Error al actualizar la URL de la imagen para el negocio {business.id}: {str(e)}")



def read_queries(file_path):
    logger.info(f"Reading queries from file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            queries = [line.strip() for line in file if line.strip()]
        logger.info(f"Successfully read {len(queries)} queries from file")
        return queries
    except Exception as e:
        logger.error(f"Error reading queries from file {file_path}: {str(e)}", exc_info=True)
        return []

def save_results(task, results, query):
    results_dir = os.path.join(settings.MEDIA_ROOT, 'scraping_results', str(task.id))
    os.makedirs(results_dir, exist_ok=True)
    file_name = f"{query.replace(' ', '_')}.json"
    file_path = os.path.join(results_dir, file_name)
    with open(file_path, 'w') as f:
        json.dump(results, f)
    logger.info(f"Saved results for query '{query}' to {file_path}")

def slugify(value):
    """
    Convierte una cadena en un slug válido para nombres de archivo.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '_', value).strip('-_')

def download_images(business, local_result):
    photos_link = local_result.get('photos_link')
    if not photos_link:
        logger.info(f"No photos link found for business {business.id}")
        return

    try:
        photos_search = GoogleSearch({
            "api_key": SERPAPI_KEY,
            "engine": "google_maps_photos",
            "data_id": local_result['data_id'],
            "hl": "en",
            "no_cache": "true"
        })
        photos_results = photos_search.get_dict()

        if 'error' in photos_results:
            logger.error(f"API Error fetching photos for business '{business.title}': {photos_results['error']}")
            return

        output_dir = os.path.join(settings.MEDIA_ROOT, 'business_images', str(business.id))
        os.makedirs(output_dir, exist_ok=True)

        # Crear un slug del nombre del negocio
        business_slug = slugify(business.title)

        # Limit 7 images
        for i, photo in enumerate(photos_results.get('photos', [])[:7]):
            image_url = photo.get('image')
            if image_url:
                try:
                    response = requests.get(image_url, timeout=10)
                    if response.status_code == 200:
                        img = PILImage.open(BytesIO(response.content))

                        # Calculate the aspect ratio
                        aspect_ratio = 3 / 2  # 3:2 aspect ratio

                        # Calculate new dimensions
                        if img.width / img.height > aspect_ratio:
                            new_width = int(img.height * aspect_ratio)
                            new_height = img.height
                        else:
                            new_width = img.width
                            new_height = int(img.width / aspect_ratio)

                        # Crop the image to 3:2
                        left = (img.width - new_width) / 2
                        top = (img.height - new_height) / 2
                        right = (img.width + new_width) / 2
                        bottom = (img.height + new_height) / 2
                        img_cropped = img.crop((left, top, right, bottom))

                        # Save the cropped image with the new naming convention
                        file_name = f"{business_slug}_{i}.jpg"
                        file_path = os.path.join(output_dir, file_name)
                        img_cropped.save(file_path, 'JPEG', quality=85)

                        local_path = os.path.join('business_images', str(business.id), file_name)
                        Image.objects.create(
                            business=business,
                            image_url=image_url,
                            local_path=local_path,
                            order=i
                        )
                        logger.info(f"Downloaded and processed image {i} for business {business.id}")

                    else:
                        logger.error(f"Failed to download image {i} for business {business.id}: HTTP {response.status_code}")
                except Exception as e:
                    logger.error(f"Error downloading image {i} for business {business.id}: {str(e)}", exc_info=True)

            time.sleep(1)  # To avoid overloading the server

        # Set the first image as the main image if it exists
        first_image = Image.objects.filter(business=business).order_by('order').first()
        if first_image:
            business.main_image = first_image.local_path
            business.save()
            logger.info(f"Set main image for business {business.id}")

    except Exception as e:
        logger.error(f"Error in download_images for business {business.id}: {str(e)}", exc_info=True)

async def translate_text(text, language="spanish"):
    if text and text.strip():
        # Usamos 'en-GB' para el inglés británico
        language_code = "en-GB" if language == "eng" else language
        
        document = doctran.parse(content=text)
        translated_doc = await document.translate(language=language_code).execute()
        return translated_doc.transformed_content
    return text

async def translate_business_info_async(business, languages=["spanish", "eng"]):
    logger.info(f"Starting translation for business {business.id}")

    # Traducción de categorías
    categories = await get_categories(business)
    for category in categories:
        for lang in languages:
            try:
                if lang == "spanish":
                    category.name_es = await translate_text(category.name, language="spanish")
                elif lang == "eng":
                    # Usamos 'eng' para mantener consistencia, pero internamente se traduce a inglés británico
                    category.name_eng = await translate_text(category.name, language="eng")
                await save_category(category)
                logger.info(f"Translated category {category.name} to {lang} for business {business.id}")
            except Exception as e:
                logger.error(f"Error translating category {category.name} to {lang} for business {business.id}: {str(e)}")

    # Traducción de información adicional
    additional_info = await get_additional_info(business)
    for info in additional_info:
        for lang in languages:
            try:
                if lang == "spanish":
                    info.key_es = await translate_text(info.key, language="spanish")
                    info.value_es = await translate_text(info.value, language="spanish")
                elif lang == "eng":
                    # Nuevamente, usamos 'eng' pero se traduce a inglés británico
                    info.key_eng = await translate_text(info.key, language="eng")
                    info.value_eng = await translate_text(info.value, language="eng")
                await save_info(info)
                logger.info(f"Translated additional info {info.key} to {lang} for business {business.id}")
            except Exception as e:
                logger.error(f"Error translating additional info {info.key} to {lang} for business {business.id}: {str(e)}")

    logger.info(f"Completed translation for business {business.id} for all languages")

def enhance_and_translate_description(business, languages=["spanish", "eng"]):
    original_description = business.description or ""
    prompt = (f"Create an appealing, not verbose, and simple reading 250-character description "
              f"for the following business:\n\nName: {business.title}\nCategory: {business.category_name}\n"
              f"Original Description: {original_description}\n\nNew Description:")

    try:
        # Mejora de la descripción
        document = doctran.parse(content=prompt)
        enhanced_doc = document.summarize(token_limit=300).execute()
        enhanced_description = enhanced_doc.transformed_content

        # Guardamos la descripción mejorada
        business.description = enhanced_description

        # Traducción a los idiomas especificados
        for lang in languages:
            translated_doc = doctran.parse(content=enhanced_description).translate(language="en-GB" if lang == "eng" else lang).execute()
            translated_description = translated_doc.transformed_content
            if lang == "spanish":
                business.description_esp = translated_description
            elif lang == "eng":
                business.description_eng = translated_description
        
        business.save()
        logger.info(f"Enhanced and translated description for business {business.id} into {', '.join(languages)}")
    except Exception as e:
        logger.error(f"Error enhancing and translating description for business {business.id}: {str(e)}")

def translate_business_info_sync(business, languages=["spanish", "eng"]):
    asyncio.run(translate_business_info_async(business, languages=languages))

def translate_business(business_id, languages=["spanish", "eng"]):
    logger.info(f"Starting translation for business {business_id}")
    try:
        business = Business.objects.get(id=business_id)
        translate_business_info_sync(business, languages=languages)
        logger.info(f"Translation completed for business {business_id} into {', '.join(languages)}")
    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} not found")
    except Exception as e:
        logger.error(f"Error translating business {business_id}: {str(e)}", exc_info=True)

def enhance_translate_and_summarize_business(business_id, languages=["spanish", "eng"]):
    logger.info(f"Starting enhancement, translation, and summarisation for business {business_id}")

    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} does not exist")
        return

    try:
        # Mejora y traducción de la descripción
        enhance_and_translate_description(business, languages=languages)
    except Exception as e:
        logger.error(f"Error enhancing and translating description for business {business_id}: {str(e)}")

    try:
        # Traducción de la información del negocio
        asyncio.run(translate_business_info_async(business, languages=languages))
    except Exception as e:
        logger.error(f"Error processing business {business_id}: {str(e)}")

    logger.info(f"Completed enhancement, translation, and summarisation for business {business_id}")
                
def fill_missing_address_components(business_data, task, query):
    # Get all businesses for this task
    task_businesses = Business.objects.filter(task=task)

    # Collect address components from all businesses
    address_components = defaultdict(set)
    for b in task_businesses:
        if b.country:
            address_components['country'].add(b.country)
        if b.state:
            address_components['state'].add(b.state)
        if b.city:
            address_components['city'].add(b.city)

    # Fill in missing components
    if not business_data['country']:
        if address_components['country']:
            business_data['country'] = next(iter(address_components['country']))
        else:
            business_data['country'] = extract_country_from_query(query)

    if not business_data['state']:
        if address_components['state']:
            business_data['state'] = next(iter(address_components['state']))
        else:
            business_data['state'] = extract_state_from_query(query)

    if not business_data['city']:
        if address_components['city']:
            business_data['city'] = next(iter(address_components['city']))
        else:
            business_data['city'] = extract_city_from_query(query)

    # If we still don't have a country, state, or city, use parts of the query as a last resort
    if not business_data['country']:
        business_data['country'] = query.split(',')[-1].strip()
    if not business_data['state']:
        business_data['state'] = query.split(',')[-2].strip() if len(query.split(',')) > 1 else ''
    if not business_data['city']:
        business_data['city'] = query.split(',')[0].strip()

    # Ensure we have at least a country
    if not business_data['country']:
        business_data['country'] = 'Unknown'

def extract_country_from_query(query):
    # Split the query into words
    words = query.split()
    
    # Check each word against the list of countries
    for word in words:
        try:
            country = pycountry.countries.search_fuzzy(word)
            if country:
                return country[0].name
        except LookupError:
            continue
    
    # If no country is found, try to geocode the entire query
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(query, addressdetails=True)
        if location and 'country' in location.raw['address']:
            return location.raw['address']['country']
    except:
        pass
    
    return ''  # Return empty string if no country is found

def extract_state_from_query(query):
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(query, addressdetails=True)
        if location and 'state' in location.raw['address']:
            return location.raw['address']['state']
    except:
        pass
    
    return ''  # Return empty string if no state is found

def extract_city_from_query(query):
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(query, addressdetails=True)
        if location and 'city' in location.raw['address']:
            return location.raw['address']['city']
    except:
        pass
    
    return ''  # Return empty string if no city is found
            
@transaction.atomic
def save_business(task, local_result, query):
    logger.info(f"Saving business data for task {task.id}")
    try:
        business_data = {
            'task': task,
            'project_id': task.project_id,
            'project_title': task.project_title,
            'main_category': task.main_category,
            'tailored_category': task.tailored_category,
            'search_string': query,
            'scraped_at': timezone.now(),
        }

        field_mapping = {
            'position': 'rank',
            'title': 'title',
            'place_id': 'place_id',
            'data_id': 'data_id',
            'data_cid': 'data_cid',
            'rating': 'average_rating',
            'reviews': 'reviews_count',
            'price': 'price',
            'type': 'category_name',
            'address': 'address',
            'phone': 'phone',
            'website': 'website',
            'description': 'description', 
            'thumbnail': 'thumbnail',
        }

        for api_field, model_field in field_mapping.items():
            if api_field in local_result:
                business_data[model_field] = local_result[api_field]

        if 'gps_coordinates' in local_result:
            business_data['latitude'] = local_result['gps_coordinates'].get('latitude')
            business_data['longitude'] = local_result['gps_coordinates'].get('longitude')

        if 'types' in local_result:
            business_data['types'] = ', '.join(local_result['types'])

        if 'operating_hours' in local_result:
            business_data['operating_hours'] = local_result['operating_hours']

        if 'service_options' in local_result:
            business_data['service_options'] = local_result['service_options']

        # Parse address using geopy
        address = local_result.get('address', '')
        geolocator = Nominatim(user_agent="your_app_name")
        try:
            location = geolocator.geocode(address, addressdetails=True)
        except (GeocoderTimedOut, GeocoderServiceError):
            location = None

        if location and location.raw.get('address'):
            address_components = location.raw['address']
            
            business_data['street'] = address_components.get('road', '')
            if 'house_number' in address_components:
                business_data['street'] = f"{address_components['house_number']} {business_data['street']}"
            
            business_data['city'] = address_components.get('city', '')
            business_data['state'] = address_components.get('state', '')
            business_data['postal_code'] = address_components.get('postcode', '')
            business_data['country'] = address_components.get('country', '')
        else:
            # If geolocation fails, store the full address in the street field
            business_data['street'] = address
            business_data['city'] = ''
            business_data['state'] = ''
            business_data['postal_code'] = ''
            business_data['country'] = ''

        # Fill in missing address components
        fill_missing_address_components(business_data, task, query)

        # Find or create the destination based on the country and state
        destination_name = f"{business_data['country']}, {business_data['state']}" if business_data['state'] else business_data['country']
        destination, created = Destination.objects.get_or_create(name=destination_name)
        business_data['destination'] = destination

        # Create or update the Business object
        business, created = Business.objects.update_or_create(
            place_id=business_data['place_id'],
            defaults=business_data
        )

        if created:
            logger.info(f"New business created: {business.title} (ID: {business.id})")
        else:
            logger.info(f"Existing business updated: {business.title} (ID: {business.id})")

        # Save categories
        Category.objects.bulk_create([
            Category(business=business, name=category)
            for category in local_result.get('categories', [])
        ], ignore_conflicts=True)

        # Save additional info
        additional_info = [
            AdditionalInfo(
                business=business,
                category=category,
                key=key,
                value=value
            )
            for category, items in local_result.get('additionalInfo', {}).items()
            for item in items
            for key, value in item.items()
        ]
        AdditionalInfo.objects.bulk_create(additional_info, ignore_conflicts=True)

        logger.info(f"Additional data saved for business {business.id}")
        
        # Queue translation task
        enhance_translate_and_summarize_business(business.id)
        logger.info(f"Translation task queued for business {business.id}")

        # Handle service options
        service_options = local_result.get('serviceOptions', {})
        if service_options:
            business.service_options = service_options
            business.save()

        logger.info(f"All business data processed and saved for business {business.id}")

        return business
    except Exception as e:
        logger.error(f"Error saving business data for task {task.id}: {str(e)}", exc_info=True)
        raise


@sync_to_async
def get_categories(business):
    return list(business.categories.all())

@sync_to_async
def get_additional_info(business):
    return list(business.additional_info.all())

@sync_to_async
def save_category(category):
    category.save()

@sync_to_async
def save_info(info):
    info.save()


def cleanup_old_tasks():
    """
    Delete tasks older than 30 days
    """
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    old_tasks = ScrapingTask.objects.filter(created_at__lt=thirty_days_ago)
    
    for task in old_tasks:
        try:
            # Delete associated files
            if task.file:
                if os.path.isfile(task.file.path):
                    os.remove(task.file.path)
            
            # Delete associated businesses and their images
            for business in task.businesses.all():
                if business.main_image:
                    if os.path.isfile(business.main_image.path):
                        os.remove(business.main_image.path)
                
                for image in business.images.all():
                    if image.image:
                        if os.path.isfile(image.image.path):
                            os.remove(image.image.path)
                    image.delete()
                
                business.delete()
            
            # Delete the task
            task.delete()
            logger.info(f"Deleted old task: {task.id}")
        except Exception as e:
            logger.error(f"Error deleting old task {task.id}: {str(e)}", exc_info=True)


def update_task_status():
    """
    Update the status of tasks based on their progress
    """
    tasks = ScrapingTask.objects.filter(status='IN_PROGRESS')
    for task in tasks:
        try:
            total_businesses = task.businesses.count()
            completed_businesses = task.businesses.filter(status='COMPLETED').count()
            
            if total_businesses > 0:
                progress = (completed_businesses / total_businesses) * 100
                task.progress = progress
                
                if progress == 100:
                    task.status = 'COMPLETED'
                    task.completed_at = timezone.now()
                
                task.save()
                logger.info(f"Updated status for task {task.id}: Progress {progress}%")
        except Exception as e:
            logger.error(f"Error updating status for task {task.id}: {str(e)}", exc_info=True)


def get_business_status(business):
    """
    Determine the status of a business based on its attributes
    """
    if business.permanently_closed:
        return 'CLOSED'
    elif business.temporarily_closed:
        return 'TEMPORARY_CLOSED'
    elif business.claim_this_business:
        return 'UNCLAIMED'
    else:
        return 'ACTIVE'


def update_business_statuses():
    """
    Update the status of all businesses
    """
    businesses = Business.objects.all()
    for business in businesses:
        try:
            new_status = get_business_status(business)
            if business.status != new_status:
                business.status = new_status
                business.save()
                logger.info(f"Updated status for business {business.id} to {new_status}")
        except Exception as e:
            logger.error(f"Error updating status for business {business.id}: {str(e)}", exc_info=True)


def calculate_business_score(business):
    """
    Calculate a score for a business based on various factors
    """
    score = 0
    if business.rating:
        score += business.rating * 20  # Max 100 points for rating

    if business.reviews_count:
        score += min(business.reviews_count, 100)  # Max 100 points for review count

    if business.images_count:
        score += min(business.images_count * 5, 50)  # Max 50 points for images

    if business.website:
        score += 50  # 50 points for having a website

    if business.phone:
        score += 25  # 25 points for having a phone number

    return min(score, 300)  # Cap the score at 300


def update_business_scores():
    """
    Update the scores of all businesses
    """
    businesses = Business.objects.all()
    for business in businesses:
        try:
            new_score = calculate_business_score(business)
            if business.score != new_score:
                business.score = new_score
                business.save()
                logger.info(f"Updated score for business {business.id} to {new_score}")
        except Exception as e:
            logger.error(f"Error updating score for business {business.id}: {str(e)}", exc_info=True)


# Utility function to get the next page token for pagination
def get_next_page_token(results):
    return results.get('serpapi_pagination', {}).get('next_page_token')


def process_next_page(task_id, query, next_page_token):
    """
    Process the next page of results for a given query
    """
    logger.info(f"Processing next page for task {task_id}, query: {query}")
    task = ScrapingTask.objects.get(id=task_id)

    try:
        params = {
            "api_key": SERPAPI_KEY,
            "engine": "google_maps",
            "type": "search",
            "q": query,
            "ll": f"@{task.latitude},{task.longitude},{task.zoom}z",
            "hl": "en",
            "start": next_page_token
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            logger.error(f"API Error for query '{query}' (next page): {results['error']}")
            return

        local_results = results.get("local_results", [])

        for local_result in local_results:
            try:
                business = save_business(task, local_result, query)
                logger.info(f"Saved business from next page: {business.title}")
            except Exception as e:
                logger.error(f"Error saving business from next page for query '{query}': {str(e)}", exc_info=True)

        # Check if there's another page
        next_token = get_next_page_token(results)
        if next_token:
            # Schedule the next page processing
            process_next_page.apply_async(args=[task_id, query, next_token], countdown=2)
        else:
            logger.info(f"Finished processing all pages for query '{query}' in task {task_id}")

    except Exception as e:
        logger.error(f"Error processing next page for task {task_id}, query '{query}': {str(e)}", exc_info=True)


def update_business_details(business_id):
    """
    Update details for a specific business using the Google Maps Place Details API
    """
    try:
        business = Business.objects.get(id=business_id)
        
        params = {
            "api_key": SERPAPI_KEY,
            "engine": "google_maps_reviews",
            "data_id": business.place_id,
            "hl": "en"
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            logger.error(f"API Error for business {business_id}: {results['error']}")
            return

        # Update business details
        business.phone = results.get('phone', business.phone)
        business.address = results.get('address', business.address)
        business.website = results.get('website', business.website)
        business.rating = results.get('rating', business.rating)
        business.reviews_count = results.get('reviews', business.reviews_count)

        # Update opening hours
        if 'hours' in results:
            OpeningHours.objects.filter(business=business).delete()
            for day, hours in results['hours'].items():
                OpeningHours.objects.create(business=business, day=day, hours=hours)

        # Update additional information
        if 'about' in results:
            AdditionalInfo.objects.filter(business=business, category='About').delete()
            for key, value in results['about'].items():
                AdditionalInfo.objects.create(business=business, category='About', key=key, value=value)

        business.save()
        logger.info(f"Updated details for business {business_id}")

    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} not found")
    except Exception as e:
        logger.error(f"Error updating details for business {business_id}: {str(e)}", exc_info=True)


def update_all_business_details():
    """
    Update details for all businesses
    """
    businesses = Business.objects.all()
    for business in businesses:
        update_business_details(business.id)
        time.sleep(1)  # Add a small delay to avoid overwhelming the API
 
def process_business_reviews(business_id):
    """
    Process reviews for a specific business
    """
    try:
        business = Business.objects.get(id=business_id)
        
        params = {
            "api_key": SERPAPI_KEY,
            "engine": "google_maps_reviews",
            "data_id": business.place_id,
            "hl": "en",
            "sort": "newest"  # Get the most recent reviews
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            logger.error(f"API Error for business reviews {business_id}: {results['error']}")
            return

        reviews = results.get('reviews', [])

        for review in reviews:
            try:
                Review.objects.update_or_create(
                    business=business,
                    author_name=review.get('user', {}).get('name', ''),
                    defaults={
                        'rating': review.get('rating'),
                        'text': review.get('snippet', ''),
                        'time': parse_review_time(review.get('date', '')),
                        'likes': review.get('likes', 0),
                        'author_image': review.get('user', {}).get('thumbnail', '')
                    }
                )
            except Exception as e:
                logger.error(f"Error saving review for business {business_id}: {str(e)}", exc_info=True)

        logger.info(f"Processed reviews for business {business_id}")

    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} not found")
    except Exception as e:
        logger.error(f"Error processing reviews for business {business_id}: {str(e)}", exc_info=True)

def parse_review_time(date_string):
    """
    Parse the review time from the given string format
    """
    try:
        return datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error(f"Error parsing date: {date_string}")
        return None


def process_all_business_reviews():
    """
    Process reviews for all businesses
    """
    businesses = Business.objects.all()
    for business in businesses:
        process_business_reviews(business.id)
        time.sleep(1)  # Add a small delay to avoid overwhelming the API


def update_business_rankings(task_id):
    """
    Update rankings for businesses within a specific task
    """
    try:
        task = ScrapingTask.objects.get(id=task_id)
        businesses = Business.objects.filter(task=task).order_by('-score')

        for rank, business in enumerate(businesses, start=1):
            business.rank = rank
            business.save()

        logger.info(f"Updated rankings for businesses in task {task_id}")

    except ScrapingTask.DoesNotExist:
        logger.error(f"Task with id {task_id} not found")
    except Exception as e:
        logger.error(f"Error updating rankings for task {task_id}: {str(e)}", exc_info=True)


def update_all_task_rankings():
    """
    Update rankings for all tasks
    """
    tasks = ScrapingTask.objects.all()
    for task in tasks:
        update_business_rankings(task.id)


def generate_task_report(task_id):
    """
    Generate a report for a specific task
    """
    try:
        task = ScrapingTask.objects.get(id=task_id)
        businesses = Business.objects.filter(task=task)

        report_data = {
            'task_id': task.id,
            'project_title': task.project_title,
            'created_at': task.created_at,
            'completed_at': task.completed_at,
            'status': task.status,
            'total_businesses': businesses.count(),
            'average_rating': businesses.aggregate(Avg('rating'))['rating__avg'],
            'top_categories': list(businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:5]),
            'businesses': []
        }

        for business in businesses:
            report_data['businesses'].append({
                'id': business.id,
                'title': business.title,
                'rating': business.rating,
                'reviews_count': business.reviews_count,
                'category': business.category_name,
                'address': business.address,
                'phone': business.phone,
                'website': business.website,
                'rank': business.rank
            })

        # Generate PDF report
        template = get_template('report_template.html')
        html = template.render(report_data)
        
        # Create a BytesIO buffer to receive PDF data
        result = BytesIO()
        
        # Generate PDF
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
        
        if not pdf.err:
            # Save the PDF report
            report_filename = f"task_report_{task.id}.pdf"
            report_path = os.path.join(settings.MEDIA_ROOT, 'reports', report_filename)
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            with open(report_path, 'wb') as f:
                f.write(result.getvalue())

            # Update task with report information
            task.report_file = f'reports/{report_filename}'
            task.save()

            logger.info(f"Generated report for task {task_id}")
        else:
            logger.error(f"Error generating PDF for task {task_id}: {pdf.err}")

    except ScrapingTask.DoesNotExist:
        logger.error(f"Task with id {task_id} not found")
    except Exception as e:
        logger.error(f"Error generating report for task {task_id}: {str(e)}", exc_info=True)

def generate_all_task_reports():
    """
    Generate reports for all completed tasks
    """
    tasks = ScrapingTask.objects.filter(status='COMPLETED', report_file__isnull=True)
    for task in tasks:
        generate_task_report(task.id)


def send_task_completion_email(task_id):
    """
    Send an email notification when a task is completed
    """
    try:
        task = ScrapingTask.objects.get(id=task_id)
        user_email = task.user.email

        subject = f"Task Completed: {task.project_title}"
        message = f"""
        Dear {task.user.username},

        Your scraping task for the project "{task.project_title}" has been completed.

        Task Details:
        - Task ID: {task.id}
        - Created At: {task.created_at}
        - Completed At: {task.completed_at}
        - Total Businesses Scraped: {task.businesses.count()}

        You can view the full results and download the report from your dashboard.

        Thank you for using our service!

        Best regards,
        Your Scraping Team
        """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )

        logger.info(f"Sent completion email for task {task_id}")

    except ScrapingTask.DoesNotExist:
        logger.error(f"Task with id {task_id} not found")
    except Exception as e:
        logger.error(f"Error sending completion email for task {task_id}: {str(e)}", exc_info=True)

@receiver(post_save, sender=ScrapingTask)
def task_status_changed(sender, instance, **kwargs):
    """
    Trigger actions when a task's status changes to 'COMPLETED'
    """
    if instance.status == 'COMPLETED' and instance.completed_at:
        # Generate report
        generate_task_report(instance.id)
        # Send email notification
        send_task_completion_email(instance.id)

