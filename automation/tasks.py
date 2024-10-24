from collections import defaultdict
from datetime import datetime
import shutil
import uuid
from celery import shared_task
from django.urls import reverse
from django.utils import timezone
from ratelimit import RateLimitException
from automation.consumers import get_log_file_path
from .models import BusinessImage, Country, Destination, Review, ScrapingTask, Business, Category, OpeningHours, AdditionalInfo, Image
from django.conf import settings 
from serpapi import GoogleSearch
import json
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
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
from requests.exceptions import RequestException
import unicodedata
import boto3
from botocore.exceptions import NoCredentialsError
import logging
import backoff
from requests.exceptions import RequestException
import backoff
import time
from requests.exceptions import RequestException
from django.utils.text import slugify


SERPAPI_KEY = settings.SERPAPI_KEY  
OPENAI_API_KEY = settings.TRANSLATION_OPENAI_API_KEY
openai.api_key = OPENAI_API_KEY   


User = get_user_model()

logger = logging.getLogger(__name__)

doctran = Doctran(openai_api_key=OPENAI_API_KEY)
 
def read_queries(file_path):
    logger.info(f"Reading queries from file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            queries = []
            for line in file:
                parts = line.strip().split('|')
                if len(parts) == 2:
                    query, coords = parts
                    queries.append({'query': query.strip(), 'll': coords.strip()})
                elif len(parts) == 1:
                    queries.append({'query': parts[0].strip(), 'll': None})
        logger.info(f"Successfully read {len(queries)} queries from file")
        return queries
    except Exception as e:
        logger.error(f"Error reading queries from file {file_path}: {str(e)}", exc_info=True)
        return []

def process_query(query_data):
    query = query_data['query']
    ll = query_data.get('ll')

    params = {
        "api_key": settings.SERPAPI_KEY,
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com",
        "q": query,
        "hl": "en",
        "no_cache": "true",
    }

    if ll:
        params["ll"] = ll

    try:
        results = fetch_search_results(params)

        if 'error' in results:
            logger.error(f"API error for query '{query}': {results['error']}")
            return None

        return results

    except (requests.RequestException, Exception) as e:
        logger.error(f"Error fetching results for query '{query}': {str(e)}")
        return None

 
# Implementación Manual de Control de Tasa
def rate_limiter(max_calls, period):
    def decorator(func):
        last_reset = [time.time()]
        call_counts = [0]

        def wrapper(*args, **kwargs):
            current_time = time.time()
            if current_time - last_reset[0] > period:
                last_reset[0] = current_time
                call_counts[0] = 0

            if call_counts[0] < max_calls:
                call_counts[0] += 1
                return func(*args, **kwargs)
            else:
                time.sleep(period - (current_time - last_reset[0]))
                return wrapper(*args, **kwargs)

        return wrapper

    return decorator

@backoff.on_exception(backoff.expo, RequestException, max_tries=5)
@rate_limiter(max_calls=10, period=60)  
def fetch_search_results(params):
    search = GoogleSearch(params)
    return search.get_dict()
 
def read_queries_from_content(file_content):
    logger.info("Reading queries from file content")
    try:
        queries = []
        for line in file_content.strip().splitlines():
            parts = line.strip().split('|')
            if len(parts) == 2:
                query, coords = parts
                queries.append({'query': query.strip(), 'll': coords.strip()})
            elif len(parts) == 1:
                queries.append({'query': parts[0].strip(), 'll': None})
        logger.info(f"Successfully read {len(queries)} queries")
        return queries
    except Exception as e:
        logger.error(f"Error reading queries from content: {str(e)}", exc_info=True)
        return []
 
def process_scraping_task(task_id, form_data=None):
    log_file_path = get_log_file_path(task_id)
    file_handler = logging.FileHandler(log_file_path)
    logger.addHandler(file_handler)

    try:
        logger.info(f"Starting scraping task {task_id}")
        task = ScrapingTask.objects.get(id=task_id)
        task.status = 'IN_PROGRESS'
        task.save()

        # Read queries from the uploaded file in DigitalOcean Spaces
        file_content = default_storage.open(task.file.name).read().decode('utf-8')
        queries = read_queries_from_content(file_content)
        logger.info(f"Total queries to process: {len(queries)}")

        total_results = 0

        for index, query_data in enumerate(queries, start=1):
            query = query_data['query']
            page_num = 1
            start_offset = 0

            while start_offset < 100:
                logger.info(f"Processing query {index}/{len(queries)}: {query} (Page {page_num})")
                query_data['start'] = start_offset

                results = process_query(query_data)

                if results is None:
                    break  # If there's an error, skip to the next query

                local_results = results.get('local_results', [])
                if not local_results:
                    logger.info(f"No results found for query '{query}' (Page {page_num})")
                    break

                logger.info(f"Processing {len(local_results)} local results for query '{query}' (Page {page_num})")
                save_results(task, results, query)

                for result_index, local_result in enumerate(local_results, start=1):
                    try:
                        with transaction.atomic():
                            logger.info(f"Saving business {result_index}/{len(local_results)} for query '{query}' (Page {page_num})")
                            business = save_business(task, local_result, query, form_data=form_data)

                            if business:
                                logger.info(f"Downloading images for business {business.id}")
                                download_images(business, local_result)
                            else:
                                logger.warning(f"Business '{local_result.get('title', 'Unknown')}' skipped due to missing country information.")

                    except Exception as e:
                        logger.error(f"Error processing business result {result_index} for query '{query}': {str(e)}", exc_info=True)
                        continue

                total_results += len(local_results)
                logger.info(f"Processed {len(local_results)} results on page {page_num} for query '{query}'")

                # Increment start_offset for the next page
                start_offset += 20
                page_num += 1
                time.sleep(2)  # Sleep between page requests to avoid overwhelming the API

            logger.info(f"Finished processing query: {query}")

        logger.info(f"Total results processed across all queries: {total_results}")

        logger.info(f"Scraping task {task_id} completed successfully")
        task.status = 'COMPLETED'
        task.completed_at = timezone.now()
        task.save()

    except ScrapingTask.DoesNotExist:
        logger.error(f"Scraping task with id {task_id} not found")
    except Exception as e:
        logger.error(f"Error in scraping task {task_id}: {str(e)}", exc_info=True)
        if 'task' in locals():
            task.status = 'FAILED'
            task.save()
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()
 
def get_next_page_token(results):
    return results.get('serpapi_pagination', {}).get('next_page_token')

def update_image_url(business, local_path, new_path):
    try:
        images = Image.objects.filter(business=business, local_path=local_path)
        if not images.exists():
            logger.warning(f"No Image found for business {business.id} with local path {local_path}")
            return
        for image in images:
            try:
                media_url = default_storage.url(new_path)
                image.image_url = media_url
                image.local_path = new_path
                image.save()
                logger.info(f"Image URL and local path updated for business {business.id}: {media_url}")
            except Exception as e:
                logger.error(f"Error updating image for business {business.id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching images for update: {str(e)}")
 
def crop_image_to_aspect_ratio(img, aspect_ratio):
    img_width, img_height = img.size
    img_aspect_ratio = img_width / img_height

    if img_aspect_ratio > aspect_ratio:
        # Image is wider than desired aspect ratio
        new_width = int(img_height * aspect_ratio)
        left = (img_width - new_width) / 2
        top = 0
        right = left + new_width
        bottom = img_height
    else:
        # Image is taller than desired aspect ratio
        new_height = int(img_width / aspect_ratio)
        left = 0
        top = (img_height - new_height) / 2
        right = img_width
        bottom = top + new_height

    return img.crop((left, top, right, bottom))
 
def get_s3_client():
    return boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
 
def download_images(business, local_result):
    photos_link = local_result.get('photos_link')
    if not photos_link:
        logger.info(f"No photos link found for business {business.id}")
        return []

    image_paths = []
    try:
        # Fetch image results from the API
        photos_search = GoogleSearch({
            "api_key": settings.SERPAPI_KEY,
            "engine": "google_maps_photos",
            "data_id": local_result['data_id'],
            "hl": "en",
            "no_cache": "true"
        })
        photos_results = photos_search.get_dict()

        if 'error' in photos_results:
            logger.error(f"API Error fetching photos for business '{business.title}': {photos_results['error']}")
            return image_paths

        # Create a slug of the business name
        business_slug = slugify(business.title)

        # Initialize the S3 client
        s3_client = get_s3_client()

        for i, photo in enumerate(photos_results.get('photos', [])):
            image_url = photo.get('image')

            # Check if the image_url already exists for this business
            if Image.objects.filter(business=business, image_url=image_url).exists():
                logger.info(f"Image already exists for business {business.id}, skipping download.")
                continue  # Skip if image already exists

            if image_url:
                try:
                    response = requests.get(image_url, timeout=10)
                    if response.status_code == 200:
                        img = PILImage.open(BytesIO(response.content))

                        # Calculate and crop to the 3:2 aspect ratio
                        aspect_ratio = 3 / 2
                        img_cropped = crop_image_to_aspect_ratio(img, aspect_ratio)

                        # Ensure file name is unique
                        file_name = f"{business_slug}_{i}.jpg"
                        file_path = f'business_images/{business.id}/{file_name}'

                        # Save the image to a temporary buffer
                        buffer = BytesIO()
                        img_cropped.save(buffer, 'JPEG', quality=85)
                        buffer.seek(0)  # Reset buffer position

                        # Upload the image using boto3 client
                        s3_client.upload_fileobj(
                            buffer,
                            settings.AWS_STORAGE_BUCKET_NAME,
                            file_path,
                            ExtraArgs={
                                'ACL': 'public-read',
                                'ContentType': 'image/jpeg'
                            }
                        )

                        # Construct the URL of the uploaded image
                        media_url = f"{settings.AWS_S3_ENDPOINT_URL}/{file_path}"

                        # Create an image object in the database
                        Image.objects.create(
                            business=business,
                            image_url=media_url,
                            local_path=file_path,
                            order=i
                        )

                        image_paths.append(file_path)
                        logger.info(f"Downloaded and processed image {i} for business {business.id}")

                    else:
                        logger.error(f"Failed to download image {i} for business {business.id}: HTTP {response.status_code}")
                except Exception as e:
                    logger.error(f"Error downloading image {i} for business {business.id}: {str(e)}", exc_info=True)

            time.sleep(1)  # To avoid overloading the server

        # Set the first image as the main image if it exists
        first_image = Image.objects.filter(business=business).order_by('order').first()
        if first_image:
            business.main_image = first_image.image_url  # Use the URL instead of local path
            business.save()
            logger.info(f"Set main image for business {business.id}")

    except Exception as e:
        logger.error(f"Error in download_images for business {business.id}: {str(e)}", exc_info=True)

    return image_paths

def save_results(task, results, query):
    try:
        file_name = f"{query.replace(' ', '_')}.json"
        file_path = f'scraping_results/{task.id}/{file_name}'

        # Convert results to JSON string
        json_content = json.dumps(results)

        # Save JSON content to DigitalOcean Spaces
        default_storage.save(file_path, ContentFile(json_content))

        logger.info(f"Saved results for query '{query}' to {file_path}")

    except Exception as e:
        logger.error(f"Error saving results for query '{query}': {str(e)}", exc_info=True)
 
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
              f"and location:{business.address}\n"
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
    """
    Fills in any missing address components using existing data from the same task or by extracting from the query.
    """
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
            logger.debug(f"Filled missing country with existing data: {business_data['country']}")
        else:
            business_data['country'] = extract_country_from_query(query)
            logger.debug(f"Filled missing country by extracting from query: {business_data['country']}")

    if not business_data['state']:
        if address_components['state']:
            business_data['state'] = next(iter(address_components['state']))
            logger.debug(f"Filled missing state with existing data: {business_data['state']}")
        else:
            business_data['state'] = extract_state_from_query(query)
            logger.debug(f"Filled missing state by extracting from query: {business_data['state']}")

    if not business_data['city']:
        if address_components['city']:
            business_data['city'] = next(iter(address_components['city']))
            logger.debug(f"Filled missing city with existing data: {business_data['city']}")
        else:
            business_data['city'] = extract_city_from_query(query)
            logger.debug(f"Filled missing city by extracting from query: {business_data['city']}")

    # If we still don't have a country, state, or city, use parts of the query as a last resort
    if not business_data['country']:
        business_data['country'] = query.split(',')[-1].strip()
        logger.warning(f"Filled missing country by splitting query: {business_data['country']}")
    if not business_data['state']:
        business_data['state'] = query.split(',')[-2].strip() if len(query.split(',')) > 1 else ''
        logger.warning(f"Filled missing state by splitting query: {business_data['state']}")
    if not business_data['city']:
        business_data['city'] = query.split(',')[0].strip()
        logger.warning(f"Filled missing city by splitting query: {business_data['city']}")

    # Ensure we have at least a country
    if not business_data['country']:
        business_data['country'] = 'Unknown'
        logger.error("Failed to fill country; set to 'Unknown'")

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
 
def parse_address_task(address):
    """
    Parses the address string and extracts components: street, city, state, postal_code, country.
    This is a placeholder implementation; ensure it accurately parses your address formats.
    """
    components = [component.strip() for component in address.split(',')]
    parsed = {
        'street': '',
        'city': '',
        'state': '',
        'postal_code': '',
        'country': ''
    }

    if len(components) >= 1:
        parsed['street'] = components[0]
    if len(components) >= 2:
        parsed['city'] = components[1]
    if len(components) >= 3:
        parsed['state'] = components[2]
    if len(components) >= 4:
        # Assume the fourth component is postal_code if it's all digits
        if components[3].isdigit():
            parsed['postal_code'] = components[3]
            if len(components) >= 5:
                parsed['country'] = components[4]
        else:
            parsed['country'] = components[3]
    elif len(components) == 3:
        parsed['country'] = components[2]

    # Optional: Use pycountry to standardize country name
    if parsed['country']:
        try:
            import pycountry
            country = pycountry.countries.search_fuzzy(parsed['country'])[0]
            parsed['country'] = country.name
        except LookupError:
            logger.warning(f"Unable to match country: {parsed['country']}")
            parsed['country'] = ''

    return parsed 

@transaction.atomic
def save_business(task, local_result, query, form_data=None):
    """
    Save business information from a scraped result or form data.
    The form_data parameter is optional and used only when business info is submitted via a form.
    """
    logger.info(f"Saving business data for task {task.id}")
    try:
        # Initialize business_data with scraped data
        business_data = {
            'task': task,
            'project_id': task.project_id,
            'project_title': task.project_title,
            'main_category': form_data['main_category'] if form_data and form_data.get('main_category') else task.main_category,
            'tailored_category': form_data['subcategory'] if form_data and form_data.get('subcategory') else task.tailored_category,
            'search_string': query,
            'scraped_at': timezone.now(),
            'level': form_data['level'] if form_data and form_data.get('level') else task.level,
        }

        # Field mapping from the scraped result to business model
        field_mapping = {
            'position': 'rank',
            'title': 'title',
            'place_id': 'place_id',
            'data_id': 'data_id',
            'data_cid': 'data_cid',
            'rating': 'rating',
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
            if local_result.get(api_field) is not None:
                business_data[model_field] = local_result[api_field]

        # Handle GPS coordinates
        if 'gps_coordinates' in local_result:
            business_data['latitude'] = local_result['gps_coordinates'].get('latitude')
            business_data['longitude'] = local_result['gps_coordinates'].get('longitude')

        # Handle types and operating hours
        if 'types' in local_result:
            business_data['types'] = ', '.join(local_result['types'])
        if 'operating_hours' in local_result:
            business_data['operating_hours'] = local_result['operating_hours']
        if 'service_options' in local_result:
            business_data['service_options'] = local_result['service_options']

        # Parse address
        address = local_result.get('address', '')
        address_components = parse_address_task(address)  # Parse the address

        # Assign address components
        business_data['street'] = address_components.get('street', '')
        business_data['city'] = address_components.get('city', '')
        business_data['state'] = address_components.get('state', '')
        business_data['postal_code'] = address_components.get('postal_code', '')
        business_data['country'] = address_components.get('country', '')

        # Fill missing address components
        fill_missing_address_components(business_data, task, query)

        # If form_data is provided, override country and destination fields
        if form_data:
            # Validate form-submitted data
            form_country_id = form_data.get('country_id')
            form_country_name = form_data.get('country_name')
            form_destination_id = form_data.get('destination_id')
            form_destination_name = form_data.get('destination_name')

            # Validate that the IDs and names correspond to existing records
            if form_country_id and form_country_name:
                try:
                    country_obj = Country.objects.get(id=form_country_id, name__iexact=form_country_name)
                except Country.DoesNotExist:
                    logger.error(f"Form-submitted Country ID {form_country_id} with name '{form_country_name}' does not exist.")
                    raise ValueError(f"Invalid country selection: {form_country_name}")

                business_data['form_country_id'] = form_country_id
                business_data['form_country_name'] = form_country_name
            else:
                business_data['form_country_id'] = None
                business_data['form_country_name'] = ''

            if form_destination_id and form_destination_name:
                try:
                    destination_obj = Destination.objects.get(id=form_destination_id, name__iexact=form_destination_name)
                except Destination.DoesNotExist:
                    logger.error(f"Form-submitted Destination ID {form_destination_id} with name '{form_destination_name}' does not exist.")
                    raise ValueError(f"Invalid destination selection: {form_destination_name}")

                business_data['form_destination_id'] = form_destination_id
                business_data['form_destination_name'] = form_destination_name
            else:
                business_data['form_destination_id'] = None
                business_data['form_destination_name'] = ''

        else:
            # Handle country and destination based on scraped data
            if business_data['country']:
                try:
                    country_obj = Country.objects.get(name__iexact=business_data['country'])
                except Country.DoesNotExist:
                    logger.error(f"Country '{business_data['country']}' does not exist.")
                    raise ValueError(f"Invalid country name: {business_data['country']}")

                # Determine destination name based on available data
                if business_data['state']:
                    destination_name = f"{business_data['country']}, {business_data['state']}"
                elif business_data['city']:
                    destination_name = business_data['city']
                else:
                    destination_name = business_data['country']

                try:
                    destination = Destination.objects.get(name__iexact=destination_name, country=country_obj)
                except Destination.DoesNotExist:
                    logger.error(f"Destination '{destination_name}' does not exist for country '{business_data['country']}'.")
                    raise ValueError(f"Invalid destination name: {destination_name}")

                business_data['destination'] = destination
            else:
                # Cannot create destination without country
                logger.error("Country information is missing, cannot create Destination.")
                raise ValueError("Country information is missing, cannot create Destination.")

        # Create or update the Business object
        business, created = Business.objects.update_or_create(
            place_id=business_data['place_id'],
            defaults=business_data
        )

        if created:
            logger.info(f"New business created: {business.title} (ID: {business.id})")
        else:
            logger.info(f"Existing business updated: {business.title} (ID: {business.id})")

        # Save categories from business_data['categories'] (assumed to be category IDs)
        categories = local_result.get('categories', [])
        for category_id in categories:
            try:
                category = Category.objects.get(id=category_id)
                business.main_category.add(category)
            except Category.DoesNotExist:
                logger.warning(f"Category ID {category_id} does not exist.")

        # Save additional info
        additional_info = [
            AdditionalInfo(
                business=business,
                key=key,
                value=value
            )
            for key, value in local_result.get('additionalInfo', {}).items()
        ]
        AdditionalInfo.objects.bulk_create(additional_info, ignore_conflicts=True)
        logger.info(f"Additional data saved for business {business.id}")

        # Handle service options
        service_options = local_result.get('serviceOptions', {})
        if service_options:
            business.service_options = service_options
            business.save()

        logger.info(f"All business data processed and saved for business {business.id}")

        # Handle image downloading separately to prevent transaction rollback
        try:
            image_paths = download_images(business, local_result)
            logger.info(f"Downloaded {len(image_paths)} images for business {business.id}")
        except Exception as e:
            logger.error(f"Error downloading images for business {business.id}: {str(e)}", exc_info=True)

        return business

    except Exception as e:
        logger.error(f"Error saving business data for task {task.id}: {str(e)}", exc_info=True)
        raise  # Re-raise the exception to trigger transaction rollback if necessary

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
