from collections import defaultdict
from datetime import datetime
import random
import shutil
import uuid
from celery import shared_task
from django.urls import reverse
from django.utils import timezone
from ratelimit import RateLimitException
import urllib
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
import csv
import pandas as pd
from django.contrib import messages

SERPAPI_KEY = settings.SERPAPI_KEY  
DEFAULT_IMAGES = settings.DEFAULT_IMAGES
OPENAI_API_KEY = settings.TRANSLATION_OPENAI_API_KEY
openai.api_key = OPENAI_API_KEY   


User = get_user_model()

logger = logging.getLogger(__name__)

doctran = Doctran(openai_api_key=OPENAI_API_KEY)

def read_queries(file_path):
    """
    Modified to handle Google Maps URLs and extract business names
    """
    logger.info(f"Reading queries from file: {file_path}")
    try:
        queries = []
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension in ['.txt']:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    # New parsing logic for Google Maps URLs
                    if 'google.com/maps/place' in line or 'google.es/maps/place' in line:
                        # Extract business name from URL
                        business_name = extract_business_name(line)
                        # Extract coordinates if available
                        coords = extract_coordinates(line)
                        
                        if business_name:
                            query_data = {'query': business_name, 'll': coords}
                            queries.append(query_data)
                    else:
                        # Original parsing logic for non-URL content
                        parts = line.strip().split('|')
                        if len(parts) == 2:
                            query, coords = parts
                            queries.append({'query': query.strip(), 'll': coords.strip()})
                        elif len(parts) == 1:
                            queries.append({'query': parts[0].strip(), 'll': None})

        return queries

    except Exception as e:
        logger.error(f"Error reading queries from file {file_path}: {str(e)}", exc_info=True)
        return []

def extract_business_name(url):
    """
    Extract business name from Google Maps URL
    """
    try:
        # Match pattern: /place/BusinessName/
        match = re.search(r'/place/([^/]+)/', url)
        if match:
            # Clean and decode the business name
            business_name = match.group(1)
            business_name = business_name.replace('+', ' ')
            business_name = urllib.parse.unquote(business_name)
            return business_name
        return None
    except Exception as e:
        logger.error(f"Error extracting business name: {str(e)}")
        return None

def extract_coordinates(url):
    """
    Extract coordinates from Google Maps URL
    """
    try:
        # Match pattern: @latitude,longitude,
        match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
        if match:
            lat, lng = match.groups()
            return f"{lat},{lng}"
        return None
    except Exception as e:
        logger.error(f"Error extracting coordinates: {str(e)}")
        return None

def process_query(query_data):
    query = query_data['query']
    data_id = query_data.get('data_id')
    ll = query_data.get('ll')
    
    if not data_id or not ll:
        logger.warning(f"Missing data_id or coordinates for query '{query}', skipping...")
        return None

    try: 
        lat, lng = ll.split(',') 
        data_param = f"!4m5!3m4!1s{data_id}!8m2!3d{lat}!4d{lng}"
        
        params = {
            "api_key": settings.SERPAPI_KEY,
            "engine": "google_maps",
            "type": "place",
            "google_domain": "google.com",
            "data": data_param,  
            "hl": "en",
            "no_cache": "true"
        }

        logger.info(f"Searching for exact place with params: {params}")

        results = fetch_search_results(params)
        
        if results and 'error' not in results:
            if 'place_results' in results:
                return {'local_results': [results['place_results']]}
            else:
                logger.warning(f"No exact match found for data_id: {data_id}")
                return None
        else:
            error_msg = results.get('error') if results else 'No results'
            logger.error(f"API error or no results for query '{query}': {error_msg}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing query '{query}': {str(e)}")
        return None



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

def read_queries_from_content(file_content):
    logger.info("Reading queries from file content")
    try:
        queries = []
        
        for line in file_content.strip().splitlines():
            line = line.strip()
            
            if 'google.es/maps/place/' in line or 'google.com/maps/place/' in line:
                name_match = re.search(r'/place/([^/]+)/', line)
                if name_match:
                    business_name = name_match.group(1)
                    business_name = urllib.parse.unquote(business_name)
                    business_name = business_name.replace('+', ' ')

                data_id_match = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', line)

                coords_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', line)
                
                if data_id_match and coords_match:
                    data_id = data_id_match.group(1)
                    lat, lng = coords_match.groups()
                    coords = f"{lat},{lng}"
                    
                    queries.append({
                        'query': business_name,
                        'data_id': data_id,
                        'll': coords,
                        'original_url': line
                    })
                    logger.info(f"Extracted business: {business_name} with data_id: {data_id} and coordinates: {coords}")
            
        logger.info(f"Successfully read {len(queries)} queries")
        return queries
        
    except Exception as e:
        logger.error(f"Error reading queries from content: {str(e)}", exc_info=True)
        return []

@backoff.on_exception(backoff.expo, RequestException, max_tries=5)
@rate_limiter(max_calls=10, period=60)  
def fetch_search_results(params):
    search = GoogleSearch(params)
    return search.get_dict()

def random_delay(min_delay=2, max_delay=5):
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)

def get_next_page_token(results):
    return results.get('serpapi_pagination', {}).get('next_page_token')
 
@shared_task(bind=True)
def process_scraping_task(self, task_id, form_data=None):
    log_file_path = get_log_file_path(task_id)
    file_handler = logging.FileHandler(log_file_path)
    logger.addHandler(file_handler)

    try:
        logger.info(f"Starting scraping task {task_id}")
        task = ScrapingTask.objects.get(id=task_id)
        task.status = 'IN_PROGRESS'
        task.save()

        queries = []

        if task.file:
            logger.info("Using uploaded file for queries.")
            file_content = default_storage.open(task.file.name).read().decode('utf-8')
            queries = read_queries_from_content(file_content)
            logger.info(f"Total queries to process from file: {len(queries)}")
        elif form_data:
            logger.info("No file uploaded, using form data to create queries.")
            country_name = form_data.get('country_name', '')
            destination_name = form_data.get('destination_name', '')
            level = form_data.get('level', '')
            main_category = form_data.get('main_category', '')
            subcategory = form_data.get('subcategory', '')
            description = form_data.get('description', '')

            query = f"{country_name}, {destination_name}, {main_category} {subcategory} {description}".strip()
            if query:
                queries.append({'query': query})

            logger.info(f"Form-based query: {query}")

        if not queries:
            logger.error("No valid queries to process.")
            return

        total_results = 0
        for index, query_data in enumerate(queries, start=1):
            query = query_data['query']
            page_num = 1
            next_page_token = None  

            while True:
                logger.info(f"Processing query {index}/{len(queries)}: {query} (Page {page_num})")

                if next_page_token:
                    query_data['start'] = next_page_token
                else:
                    query_data.pop('start', None) 

                results = process_query(query_data)

                if results is None:
                    break 

                local_results = results.get('local_results', [])
                if not local_results:
                    logger.info(f"No results found for query '{query}' (Page {page_num})")
                    break

                logger.info(f"Processing {len(local_results)} local results for query '{query}' (Page {page_num})")
                logger.info(f"Local result data: {local_results}")

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

                next_page_token = get_next_page_token(results)
                if next_page_token:
                    logger.info(f"Next page token found: {next_page_token}")
                    page_num += 1
                    random_delay(min_delay=2, max_delay=20)
                else:
                    logger.info(f"No next page token found for query '{query}'")
                    break 

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
        task.status = 'FAILED'
        task.save()
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()
 
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

        new_width = int(img_height * aspect_ratio)
        left = (img_width - new_width) / 2
        top = 0
        right = left + new_width
        bottom = img_height
    else:

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

        # Limit photos to a maximum of DEFAULT_IMAGES images
        photos = photos_results.get('photos', [])[:DEFAULT_IMAGES]
        if not photos:
            logger.info(f"No photos found for business {business.id} in fetched results")
            return image_paths

        # Create a slug of the business name
        business_slug = slugify(business.title)

        # Initialize the S3 client
        s3_client = get_s3_client()

        for i, photo in enumerate(photos):
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

                        # Create an image object in the database only if it doesn't exist
                        if not Image.objects.filter(business=business, local_path=file_path).exists():
                            Image.objects.create(
                                business=business,
                                image_url=image_url,
                                local_path=file_path,
                                order=i
                            )
                            image_paths.append(file_path)
                            logger.info(f"Downloaded and processed image {i} for business {business.id}")

                        else:
                            logger.info(f"Image with local path {file_path} already exists for business {business.id}, skipping.")

                    else:
                        logger.error(f"Failed to download image {i} for business {business.id}: HTTP {response.status_code}")
                except Exception as e:
                    logger.error(f"Error downloading image {i} for business {business.id}: {str(e)}", exc_info=True)

            random_delay(min_delay=2, max_delay=20)  

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

        json_content = json.dumps(results)

        default_storage.save(file_path, ContentFile(json_content))

        logger.info(f"Saved results for query '{query}' to {file_path}")

    except Exception as e:
        logger.error(f"Error saving results for query '{query}': {str(e)}", exc_info=True)


#####################DESCRIPTION TRANSLATE##################################
 
def translate_text(text, language="spanish"):
    if text and text.strip():
        language_code = "en-GB" if language == "eng" else language
        try:
            document = doctran.parse(content=text)
            translated_doc = document.translate(language=language_code).execute()
            return translated_doc.transformed_content
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            return None
    return text
 
def enhance_and_translate_description(business, languages=["spanish", "eng"]):
    """
    Enhances the business description and translates it into specified languages.
    Uses batch processing and concurrent API calls for better performance.
    """
    if not business.description or not business.description.strip():
        logger.info(f"No base description available for business {business.id}. Enhancement and translation skipped.")
        return False

    try:
        # Prepare system messages for different tasks
        messages = {
            'enhance': [
                {"role": "system", "content": "You are an expert SEO content writer."},
                {"role": "user", "content": f"""
                    Write a detailed description of exactly 220 words.
                    About: '{business.title}', a '{business.category_name}' in '{business.city}, {business.country}'.
                    Requirements:
                    - SEO optimized
                    - '{business.title}' or synonyms in first paragraph
                    - Use '{business.title}' twice
                    - 80% sentences under 20 words
                    - Formal tone
                    - Avoid: 'vibrant', 'in the heart of', 'in summary'
                    - Include blank lines between paragraphs
                """}
            ],
            'translate_es': [
                {"role": "system", "content": "You are an expert Spanish translator."},
                {"role": "user", "content": "Translate to Spanish, preserving structure and tone:"}
            ],
            'translate_en': [
                {"role": "system", "content": "You are an expert British English localizer."},
                {"role": "user", "content": "Convert to British English, using appropriate spellings and conventions:"}
            ]
        }

        # Function to make API calls with retry logic
        def call_openai_with_retry(messages, retries=3, delay=2):
            for attempt in range(retries):
                try:
                    return openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",  # Use 3.5-turbo for better performance/cost balance
                        messages=messages,
                        temperature=0.3,
                        max_tokens=800,
                        presence_penalty=0.0,
                        frequency_penalty=0.0
                    )
                except openai.error.RateLimitError:
                    if attempt == retries - 1:
                        raise
                    time.sleep(delay * (attempt + 1))
                except openai.error.OpenAIError as e:
                    if attempt == retries - 1:
                        raise
                    time.sleep(delay)

        response = call_openai_with_retry(messages['enhance'])
        enhanced_description = response['choices'][0]['message']['content'].strip()
        business.description = enhanced_description

        if languages:
            combined_prompt = (
                "Translate the following text into both Spanish and British English. "
                "Provide both translations separated by [SPLIT]:\n\n"
                f"{enhanced_description}"
            )
            
            response_translations = call_openai_with_retry([
                {"role": "system", "content": "You are an expert multilingual translator."},
                {"role": "user", "content": combined_prompt}
            ])
            
            translations = response_translations['choices'][0]['message']['content'].split('[SPLIT]')
            
            if len(translations) >= 2:
                if "spanish" in languages:
                    business.description_esp = translations[0].strip()
                if "eng" in languages:
                    business.description_eng = translations[1].strip()

        business.save()
        logger.info(f"Enhanced and translated description for business {business.id} into {', '.join(languages)}")
        return True

    except Exception as e:
        logger.error(f"Error processing business {business.id}: {str(e)}", exc_info=True)
        return False



def generate_additional_sentences_openai(business, word_deficit):
    """
    Generates additional content using OpenAI to meet the required word count.
    """
    prompt = (
        f"Write additional content of about {word_deficit} words to describe:\n"
        f"'{business.title}', a '{business.category_name}' located in '{business.city}, {business.country}'.\n"
        f"Focus on its unique features, offerings, and appeal to customers.\n"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert content writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response['choices'][0]['message']['content'].strip()
    except openai.error.OpenAIError as e:
        logger.error(f"Error generating additional sentences: {str(e)}", exc_info=True)
        return ""


def translate_text_openai(text, target_language):
    """
    Translates the given text into the specified language using OpenAI's newer models.
    """
    prompt = (
        f"Translate the following text into {target_language}:\n\n"
        f"{text}\n\n"
        f"Preserve the structure, formatting, and tone of the original text."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert translator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response['choices'][0]['message']['content'].strip()
    except openai.error.OpenAIError as e:
        logger.error(f"Error translating text: {str(e)}", exc_info=True)
        return ""


def generate_additional_sentences(business, word_deficit):
    """
    Generates additional sentences to meet the required word count.
    """
    try:
        prompt = (
            f"Generate additional content of about {word_deficit} words to describe:\n"
            f"'{business.title}', a '{business.category_name}' located in '{business.city}, {business.country}'.\n"
            f"Focus on its unique features, offerings, and appeal to customers."
        )
        document = doctran.parse(content=prompt)
        additional_sentences = document.summarize(token_limit=word_deficit * 2).transformed_content.strip()
        return additional_sentences
    except Exception as e:
        logger.error(f"Error generating additional sentences: {str(e)}", exc_info=True)
        return ""


def translate_business_info(business, languages=["spanish", "eng"]):
    logger.info(f"Starting translation for business {business.id}")

    try:
        for lang in languages:
            language_code = "en-GB" if lang == "eng" else lang

            if business.title:
                translated_title = translate_text(business.title, language=language_code)
                if lang == "spanish":
                    business.title_esp = translated_title
                elif lang == "eng":
                    business.title_eng = translated_title

            if business.description:
                translated_description = translate_text(business.description, language=language_code)
                if lang == "spanish":
                    business.description_esp = translated_description
                elif lang == "eng":
                    business.description_eng = translated_description

        business.save()
        logger.info(f"Completed translation for business {business.id} into {', '.join(languages)}")
    except Exception as e:
        logger.error(f"Error translating business {business.id}: {str(e)}", exc_info=True)


def enhance_translate_and_summarize_business(business_id, languages=["spanish", "eng"]):
    logger.info(f"Starting enhancement, translation, and summarisation for business {business_id}")

    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error retrieving business {business_id}: {str(e)}", exc_info=True)
        return False

    try:
        # Enhance and translate the description
        enhance_and_translate_description(business, languages=languages)
    except Exception as e:
        logger.error(f"Error enhancing and translating description for business {business_id}: {str(e)}", exc_info=True)
        return False

    try:
        # Translate business information
        translate_business_info(business, languages=languages)
    except Exception as e:
        logger.error(f"Error processing business {business_id}: {str(e)}", exc_info=True)
        return False

    logger.info(f"Completed enhancement, translation, and summarisation for business {business_id}")
    return True


#####################DESCRIPTION TRANSLATE##################################

def extract_address_components(address_string):
    """
    Extract address components from a full address string.
    Example: "Carrer del Call, 17, Ciutat Vella, 08002 Barcelona, Spain"
    """
    components = {
        'street_address': '',
        'postal_code': ''
    }
    
    if not address_string:
        return components

    try:
        # First, try to find the postal code (5 digits)
        postal_code_match = re.search(r'\b\d{5}\b', address_string)
        
        if postal_code_match:
            components['postal_code'] = postal_code_match.group(0)
            # Split address by comma and take parts before the postal code
            parts = [part.strip() for part in address_string.split(',')]
            
            # Find which part contains the postal code
            postal_code_part_index = None
            for i, part in enumerate(parts):
                if components['postal_code'] in part:
                    postal_code_part_index = i
                    break
            
            if postal_code_part_index is not None:
                # Take all parts before the postal code for the street address
                components['street_address'] = ', '.join(parts[:postal_code_part_index]).strip()
            else:
                components['street_address'] = parts[0]
        else:
            # If no postal code found, take first part as street
            parts = [part.strip() for part in address_string.split(',')]
            components['street_address'] = parts[0]
            
        logger.info(f"Parsed address components from: {address_string}")
        logger.info(f"Street: {components['street_address']}")
        logger.info(f"Postal Code: {components['postal_code']}")
        
    except Exception as e:
        logger.error(f"Error parsing address: {str(e)}")
        parts = address_string.split(',')
        components['street_address'] = parts[0] if parts else address_string
    
    return components

def fill_missing_address_components(business_data, task, query, form_data=None):
    """
    Fills the missing address components, prioritizing form data if provided.
    """
    logger.info("Filling missing address components...")
 
    if form_data:
        business_data['country'] = form_data.get('country', business_data.get('country', ''))
        business_data['city'] = form_data.get('destination', business_data.get('city', ''))
        business_data['level'] = form_data.get('level', business_data.get('level', ''))
        business_data['main_category'] = form_data.get('main_category', business_data.get('main_category', ''))
        business_data['tailored_category'] = form_data.get('subcategory', business_data.get('tailored_category', ''))
 
    if not business_data.get('country'):
        business_data['country'] = query.split(',')[-1].strip()
    
    if not business_data.get('city'):
        business_data['city'] = query.split(',')[0].strip()

    logger.info(f"Final address components:")
    logger.info(f"Street: {business_data.get('address', '')}")
    logger.info(f"Postal Code: {business_data.get('postal_code', '')}")
    logger.info(f"City: {business_data.get('city', '')}")
    logger.info(f"Country: {business_data.get('country', '')}")
 
 
@transaction.atomic
def save_business(task, local_result, query, form_data=None):
    logger.info(f"Saving business data for task {task.id}")
    try: 
        business_data = {
            'task': task,
            'project_id': task.project_id,
            'project_title': task.project_title,
            'main_category': form_data.get('main_category', task.main_category),
            'tailored_category': form_data.get('subcategory', task.tailored_category),
            'search_string': query,
            'scraped_at': timezone.now(),
            'level': form_data.get('level', task.level),
            'country': form_data.get('country_name', ''),
            'city': form_data.get('destination_name', ''),
            'state': '',   
            'form_country_id': form_data.get('country_id'),
            'form_country_name': form_data.get('country_name', ''),
            'form_destination_id': form_data.get('destination_id'),
            'form_destination_name': form_data.get('destination_name', ''),
            'destination_id': form_data.get('destination_id'),
        }

        logger.info(f"Local result data: {local_result}") 
        if 'address' in local_result:
            full_address = local_result['address']
            business_data['address'] = full_address  
 
            address_components = extract_address_components(full_address)
 
            # Set street and postal_code
            business_data['street'] = address_components['street_address']
            business_data['postal_code'] = address_components['postal_code']
            
            logger.info(f"Extracted address components:")
            logger.info(f"Full Address: {full_address}")
            logger.info(f"Street: {business_data['street']}")
            logger.info(f"Postal Code: {business_data['postal_code']}")

        field_mapping = {
            'position': 'rank',
            'title': 'title',
            'place_id': 'place_id',
            'data_id': 'data_id',
            'data_cid': 'data_cid',
            'rating': 'rating',
            'reviews': 'reviews_count',
            'price': 'price',
            'types': 'type',
            'address': 'address',
            'postal_code': 'postal_code',
            'city': 'city',
            'phone': 'phone',
            'website': 'website',
            'description': 'description',
            'thumbnail': 'thumbnail',
        }

        for api_field, model_field in field_mapping.items():
            if local_result.get(api_field) is not None:
                business_data[model_field] = local_result[api_field]
        logger.info(f"Business data to be saved: {business_data}")
 
        if 'gps_coordinates' in local_result:
            business_data['latitude'] = local_result['gps_coordinates'].get('latitude')
            business_data['longitude'] = local_result['gps_coordinates'].get('longitude')

        if 'type' in local_result: 
            business_data['types'] = ', '.join(local_result['type'])
        elif 'types' in local_result: 
            business_data['types'] = ', '.join(local_result['types'])
 
       
        ordered_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        if 'hours' in local_result:
            hours_data = local_result['hours']
            formatted_hours = {day: None for day in ordered_days}  # Initialize with None values

            if isinstance(hours_data, dict):
                # If hours_data is already a dictionary
                for day in ordered_days:
                    formatted_hours[day] = hours_data.get(day, None)
            
            elif isinstance(hours_data, list):
                # If hours_data is a list of schedules
                for schedule_item in hours_data:
                    if isinstance(schedule_item, dict):
                        # Update formatted_hours with any found schedules
                        formatted_hours.update(schedule_item)

            business_data['operating_hours'] = formatted_hours
            logger.info(f"Formatted hours data: {formatted_hours}")


        elif 'operating_hours' in local_result:
            hours_data = local_result['operating_hours']
            formatted_hours = {}
            ordered_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            
            if isinstance(hours_data, dict):
                formatted_hours = {
                    day: hours_data.get(day, None) 
                    for day in ordered_days
                }
            elif isinstance(hours_data, list):
                for day in ordered_days:
                    day_schedule = next(
                        (schedule for schedule in hours_data 
                        if isinstance(schedule, str) and day in schedule.lower()),
                        None
                    )
                    formatted_hours[day] = day_schedule
            
            business_data['operating_hours'] = formatted_hours

        if 'extensions' in local_result:
            extensions = local_result['extensions']
            if isinstance(extensions, list):
                cleaned_extensions = []
                for category_dict in extensions:
                    if isinstance(category_dict, dict):
                        for category, values in category_dict.items():
                            if values:  
                                cleaned_extensions.append({category: values})
                business_data['service_options'] = cleaned_extensions
                logger.info(f"Processed extensions data: {cleaned_extensions}")
        elif 'service_options' in local_result:
            service_opts = local_result['service_options']
            if isinstance(service_opts, dict):
                formatted_options = [{
                    'general': [
                        f"{key}: {'Yes' if value else 'No'}"
                        for key, value in service_opts.items()
                    ]
                }]
                business_data['service_options'] = formatted_options
 
        fill_missing_address_components(business_data, task, query, form_data=form_data)

        if 'place_id' not in business_data:
            logger.warning(f"Skipping business entry for task {task.id} due to missing 'place_id'")
            return None   
    
        business, created = Business.objects.update_or_create(
            place_id=business_data['place_id'],
            defaults=business_data
        )
        if created:
            logger.info(f"New business created: {business.title} (ID: {business.id})")
        else:
            logger.info(f"Existing business updated: {business.title} (ID: {business.id})")
 
        categories = local_result.get('categories', [])
        for category_id in categories:
            try:
                category = Category.objects.get(id=category_id)
                business.main_category.add(category)
            except Category.DoesNotExist:
                logger.warning(f"Category ID {category_id} does not exist.")

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
 
        service_options = local_result.get('serviceOptions', {})
        if service_options:
            business.service_options = service_options
            business.save()

        logger.info(f"All business data processed and saved for business {business.id}")
        logger.info(f"Address components saved - Street: {business.street}, "
            f"Postal Code: {business.postal_code}, City: {business.city}")
 
        try:
            image_paths = download_images(business, local_result)
            logger.info(f"Downloaded {len(image_paths)} images for business {business.id}")
        except Exception as e:
            logger.error(f"Error downloading images for business {business.id}: {str(e)}", exc_info=True)

        return business

    except Exception as e:
        logger.error(f"Error saving business data for task {task.id}: {str(e)}", exc_info=True)
        raise  # Re-raise the exception to trigger transaction rollback if necessary

def generate_full_address(business_data):
    """
    Generates a full address string from individual components.
    """
    address_components = [
        business_data.get('address'),
        business_data.get('city'),
        f"{business_data.get('state', '')} {business_data.get('postal_code', '')}".strip(),
        business_data.get('country')
    ]
    return ", ".join(filter(None, address_components))  


def format_operating_hours(operating_hours):
    """
    Handles multiple operating hours formats and converts them to the required format with en dash
    """
    if not operating_hours:
        return None

    def parse_time(time_str):
        """Parse a single time component"""
        if not time_str:
            return None, None, None
            
        time_str = time_str.replace('\u202f', ' ').strip()
        parts = time_str.split(' ')
        
        if len(parts) == 2:
            time_part, period = parts
        else:
            time_part = parts[0]
            period = None
            
        if ':' in time_part:
            try:
                hour, minute = map(int, time_part.split(':'))
            except ValueError:
                return None, None, None
        else:
            try:
                hour = int(time_part)
                minute = 0
            except ValueError:
                return None, None, None
            
        return hour, minute, period

    def format_single_range(time_range):
        """Format a single time range with proper en dash"""
        if not time_range or time_range.lower() in ['closed', 'none'] or time_range is None:
            return 'Closed'
            
        try:
            # Handle multiple ranges
            if ',' in str(time_range):
                ranges = [r.strip() for r in str(time_range).split(',')]
                return ', '.join(format_single_range(r) for r in ranges)
            
            # Standardize format
            time_range = str(time_range).replace('–', ' to ').replace('-', ' to ').replace('\u202f', ' ')
            
            # Split into start and end times
            if ' to ' in time_range:
                start_raw, end_raw = [t.strip() for t in time_range.split(' to ')]
            else:
                parts = time_range.split(' ')
                split_index = None
                for i, part in enumerate(parts):
                    if 'PM' in part or 'AM' in part:
                        split_index = i + 1
                        break
                
                if split_index is None or split_index >= len(parts):
                    return 'No hours specified'
                    
                start_raw = ' '.join(parts[:split_index])
                end_raw = ' '.join(parts[split_index:])
            
            # Parse times
            start_hour, start_minute, start_period = parse_time(start_raw)
            end_hour, end_minute, end_period = parse_time(end_raw)
            
            # Handle invalid times
            if None in [start_hour, end_hour]:
                return 'No hours specified'
            
            # Handle period inheritance and conversion
            if not start_period and end_period:
                start_period = end_period
            if not end_period and start_period:
                end_period = start_period
            if not start_period and not end_period:
                start_period = end_period = 'PM'
            
            # Convert to 24-hour format for comparison
            def to_24hour(hour, minute, period):
                if period.upper() == 'PM' and hour != 12:
                    hour += 12
                elif period.upper() == 'AM' and hour == 12:
                    hour = 0
                return hour, minute
            
            start_hour, start_minute = to_24hour(start_hour, start_minute, start_period)
            end_hour, end_minute = to_24hour(end_hour, end_minute, end_period)
            
            # Handle midnight case (12 AM)
            if end_hour == 0 and end_minute == 0:
                end_hour = 23
                end_minute = 59
            
            # Convert back to 12-hour format
            def to_12hour(hour, minute):
                period = 'AM'
                if hour >= 12:
                    period = 'PM'
                    if hour > 12:
                        hour -= 12
                elif hour == 0:
                    hour = 12
                return f"{hour:02d}:{minute:02d} {period}"
            
            formatted_start = to_12hour(start_hour, start_minute)
            formatted_end = to_12hour(end_hour, end_minute)
            
            return f"{formatted_start} – {formatted_end}"
            
        except Exception as e:
            logger.error(f"Error formatting single range '{time_range}': {str(e)}")
            return 'No hours specified'

    try:
        formatted_hours = {}
        
        # Handle dictionary format
        if isinstance(operating_hours, dict):
            for day, hours in operating_hours.items():
                # Handle None, 'None', empty strings, and 'closed'
                if hours is None or str(hours).strip().lower() in ['none', '', 'closed']:
                    formatted_hours[day] = 'Closed'
                    continue
                
                try:
                    if isinstance(hours, str):
                        if ',' in hours:
                            ranges = [r.strip() for r in hours.split(',')]
                            formatted_ranges = []
                            for r in ranges:
                                formatted_range = format_single_range(r)
                                if formatted_range != 'No hours specified':
                                    formatted_ranges.append(formatted_range)
                            formatted_hours[day] = ', '.join(formatted_ranges) if formatted_ranges else 'Closed'
                        else:
                            formatted_range = format_single_range(hours.strip())
                            formatted_hours[day] = formatted_range if formatted_range != 'No hours specified' else 'Closed'
                except Exception as e:
                    logger.error(f"Error formatting hours for {day}: {str(e)}")
                    formatted_hours[day] = 'Closed'
        
        logger.info(f"Successfully formatted operating hours: {formatted_hours}")
        return formatted_hours
        
    except Exception as e:
        logger.error(f"Error in format_operating_hours: {str(e)}")
        return dict((day, 'Closed') for day in operating_hours.keys())

 
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
        random_delay(min_delay=2, max_delay=20) 
 
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
        random_delay(min_delay=2, max_delay=20)  
 
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
