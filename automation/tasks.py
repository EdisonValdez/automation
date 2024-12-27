from collections import defaultdict
from datetime import datetime
import random
import shutil
import string
from typing import Optional
import uuid
from celery import shared_task
from django.urls import reverse
from django.utils import timezone
from ratelimit import RateLimitException
import urllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from automation.consumers import get_log_file_path 
from .models import BusinessImage, Country, Destination, HourlyBusyness, PopularTimes, Review, ScrapingTask, Business, Category, OpeningHours, AdditionalInfo, Image
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
        logger.info(f"Starting Sites Gathering task {task_id}")
        task = ScrapingTask.objects.get(id=task_id)
        task.status = 'IN_PROGRESS'
        task.save()

        queries = []

        if form_data:
            image_count = form_data.get('image_count', 3)
            logger.info(f"Using image count from form data: {image_count}")
        

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
            image_count = form_data.get('image_count', 3)

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
                                download_images(business, local_result, image_count=image_count)
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

        logger.info(f"Sites Gathering task {task_id} completed successfully")
        task.status = 'COMPLETED'
        task.completed_at = timezone.now()
        task.save()

    except ScrapingTask.DoesNotExist:
        logger.error(f"Sites Gathering task with id {task_id} not found")
    except Exception as e:
        logger.error(f"Error in Sites Gathering task {task_id}: {str(e)}", exc_info=True)
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
 
def download_images(business, local_result, image_count=3):
    photos_link = local_result.get('photos_link')
    if not photos_link:
        logger.info(f"No photos link found for business {business.id}")
        return []

    try:
        image_count = int(image_count)
        logger.info(f"Processing download with image count: {image_count}")
    except (TypeError, ValueError):
        image_count = 3
        logger.warning(f"Invalid image count provided, using default: {image_count}")
    
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

        all_photos = photos_results.get('photos', [])
        photos = all_photos[:image_count]
        
        logger.info(f"Found {len(all_photos)} total photos, downloading {len(photos)} as per image_count: {image_count}")
 
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


def call_openai_with_retry(messages, model="gpt-3.5-turbo", temperature=0.3, max_tokens=800, presence_penalty=0.0, frequency_penalty=0.0, retries=2, delay=1):
    for attempt in range(retries):
        try:
            return openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty
            )
        except openai.error.RateLimitError as e:
            logger.warning(f"Rate limit error on attempt {attempt+1}: {str(e)}")
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
        except openai.error.OpenAIError as e:
            logger.warning(f"OpenAI error on attempt {attempt+1}: {str(e)}")
            if attempt == retries - 1:
                raise
            time.sleep(delay)
  
def translate_text_openai(text, target_language):
    if not text or text.strip() == "":
        logger.warning("Empty text provided for translation")
        return ""

    language_map = {
        "eng": "British English",
        "spanish": "Spanish"
    }

    if target_language not in language_map:
        logger.error(f"Unsupported target language: {target_language}")
        return ""

    messages = [
        {
            "role": "system",
            "content": f"You are an expert translator. Translate the following text to {language_map[target_language]}. Maintain the original meaning, tone, and formatting. Do not add any explanatory text or language markers."
        },
        {
            "role": "user",
            "content": text
        }
    ]

    try:
        response = call_openai_with_retry(
            messages=messages,
            max_tokens=len(text.split()) * 2,  
            temperature=0.3,  
            presence_penalty=0.0,
            frequency_penalty=0.0
        )
        
        translated_text = response['choices'][0]['message']['content'].strip()
        logger.info(f"Successfully translated text to {target_language}")
        return translated_text

    except Exception as e:
        logger.error(f"Translation error for {target_language}: {str(e)}", exc_info=True)
        return ""

def enhance_and_translate_description(business, languages=["spanish", "eng"]):
    """
    Enhances the business description and translates it into specified languages.
    Ensures proper distinction between US and UK English.
    """
    if not business.description or not business.description.strip():
        logger.info(f"No base description available for business {business.id}")
        return False

    try: 
        enhance_messages = [
            {"role": "system", "content": "You are an expert SEO content writer specializing in American English."},
            {"role": "user", "content": f"""
                Write a detailed description of EXACTLY 220 words using American English.
                Business: '{business.title}'
                Category: '{business.category_name}'
                Location: '{business.city}, {business.country}'

                Requirements:
                - EXACTLY 220 words
                - Use American English spelling and terms (e.g., 'rental', 'center', 'customize')
                - Include '{business.title}' in first paragraph
                - Use '{business.title}' exactly twice
                - 80% sentences under 20 words
                - Formal American tone
                - SEO optimized
                - Avoid: 'vibrant', 'in the heart of', 'in summary'
            """}
        ]
 
        response = call_openai_with_retry(
            messages=enhance_messages,
            model="gpt-3.5-turbo",
            max_tokens=800,
            temperature=0.7
        )

        us_description = response['choices'][0]['message']['content'].strip()
        business.description = us_description
 
        uk_messages = [
            {"role": "system", "content": "You are an expert translator specializing in British English adaptations."},
            {"role": "user", "content": f"""
                Convert the following American English text to British English.
                Make sure to:
                1. Change spellings (e.g., 'color' to 'colour', 'customize' to 'customise')
                2. Change terms:
                   - 'rental' to 'hire'
                   - 'center' to 'centre'
                   - 'apartment' to 'flat'
                   - 'vacation' to 'holiday'
                   - 'downtown' to 'city centre'
                   - 'parking lot' to 'car park'
                   - 'elevator' to 'lift'
                   - 'store' to 'shop'
                3. Adjust phrases to British usage
                4. Maintain the exact same length and structure
                
                Text to convert:
                {us_description}
            """}
        ]
 
        uk_response = call_openai_with_retry(
            messages=uk_messages,
            model="gpt-3.5-turbo",
            max_tokens=800,
            temperature=0.3
        )

        uk_description = uk_response['choices'][0]['message']['content'].strip()
        business.description_eng = uk_description
 
        if "spanish" in languages:
            spanish_messages = [
                {"role": "system", "content": "You are an expert Spanish translator."},
                {"role": "user", "content": f"""
                    Translate this text to Spanish, maintaining the formal tone and marketing style:
                    {us_description}
                """}
            ]

            spanish_response = call_openai_with_retry(
                messages=spanish_messages,
                model="gpt-3.5-turbo",
                max_tokens=800,
                temperature=0.3
            )

            spanish_description = spanish_response['choices'][0]['message']['content'].strip()
            business.description_esp = spanish_description

        business.save()
        logger.info(f"Successfully enhanced and translated descriptions for business {business.id}")
        return True

    except Exception as e:
        logger.error(f"Error in enhance_and_translate_description for business {business.id}: {str(e)}", exc_info=True)
        return False
 
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
        additional_sentences = document.summarize(
            token_limit=word_deficit * 2
        ).transformed_content.strip()

        return additional_sentences
    except Exception as e:
        logger.error(f"Error generating additional sentences: {str(e)}", exc_info=True)
        return ""

def translate_business_info(business, languages=["spanish", "eng"]):
    """
    Handles the complete business translation process including validation and status updates.
    """
    logger.info(f"Starting translation process for business {business.id}")
    
    try:
        # Case 1: Validate existing content
        if not validate_business_content(business):
            logger.warning(f"Business {business.id} content validation failed")
            return False

        # Case 2: Process title translations if needed
        if business.title and (not business.title_eng or not business.title_esp):
            success = translate_business_titles(business, languages)
            if not success:
                logger.error(f"Failed to translate titles for business {business.id}")
                return False

        # Case 3: Process description translations
        if business.description:
            word_count = len(business.description.split())
            
            # Enhancement needed if description is too short
            if word_count < 220:
                logger.info(f"Business {business.id} description needs enhancement ({word_count} words)")
                success = enhance_and_translate_description(business)
                if not success:
                    return False

            # Process translations
            success = process_business_translations(business, languages)
            if not success:
                return False

        # Final validation and status update
        if validate_translations(business):
            business.status = 'REVIEWED'
            business.save(update_fields=['status'])
            logger.info(f"Successfully completed translations for business {business.id}")
            return True
        else:
            logger.error(f"Final validation failed for business {business.id}")
            return False

    except Exception as e:
        logger.error(f"Error in translation process for business {business.id}: {str(e)}", exc_info=True)
        return False

def validate_business_content(business):
    """
    Validates the basic content requirements for a business.
    """
    if not business.title:
        logger.error(f"Business {business.id} missing title")
        return False

    if not business.description and not business.description_eng and not business.description_esp:
        logger.error(f"Business {business.id} missing all descriptions")
        return False

    return True

def translate_business_titles(business, languages):
    """
    Handles the translation of business titles.
    """
    try:
        for lang in languages:
            if lang == "spanish" and not business.title_esp:
                translated_title = translate_text_openai(business.title, "spanish")
                if translated_title:
                    business.title_esp = translated_title
                    
            elif lang == "eng" and not business.title_eng:
                translated_title = translate_text_openai(business.title, "eng")
                if translated_title:
                    business.title_eng = translated_title

        business.save(update_fields=['title_esp', 'title_eng'])
        return True

    except Exception as e:
        logger.error(f"Error translating titles for business {business.id}: {str(e)}", exc_info=True)
        return False

def process_business_translations(business, languages):
    """
    Processes translations for business descriptions.
    """
    try:
        for lang in languages:
            if lang == "spanish" and not business.description_esp:
                translated_desc = translate_text_openai(business.description, "spanish")
                if translated_desc:
                    business.description_esp = translated_desc
                    
            elif lang == "eng" and not business.description_eng:
                translated_desc = translate_text_openai(business.description, "eng")
                if translated_desc:
                    business.description_eng = translated_desc

        business.save(update_fields=['description_esp', 'description_eng'])
        return True

    except Exception as e:
        logger.error(f"Error processing translations for business {business.id}: {str(e)}", exc_info=True)
        return False

def validate_translations(business):
    """
    Performs final validation of all translated content.
    """
    required_fields = {
        'title': business.title,
        'description': business.description,
        'title_eng': business.title_eng,
        'title_esp': business.title_esp,
        'description_eng': business.description_eng,
        'description_esp': business.description_esp
    }

    invalid_fields = []
    for field, value in required_fields.items():
        if not value or value.lower() in ['no description', 'none', '']:
            invalid_fields.append(field)

    if invalid_fields:
        logger.error(f"Business {business.id} missing or invalid fields: {', '.join(invalid_fields)}")
        return False

    return True

def enhance_translate_and_summarize_business(business_id, languages=["spanish", "eng"]):
    """
    Main function to coordinate the enhancement, translation, and summarization process.
    """
    logger.info(f"Starting enhancement, translation, and summarization for business {business_id}")
    
    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error retrieving business {business_id}: {str(e)}", exc_info=True)
        return False

    try:
        # Step 1: Initial validation
        if not validate_business_content(business):
            logger.error(f"Initial validation failed for business {business_id}")
            return False

        # Step 2: Generate description if needed
        if not business.description or business.description.lower() in ['no description', 'none', '']:
            logger.info(f"Generating new description for business {business_id}")
            success = generate_new_description(business)
            if not success:
                logger.error(f"Failed to generate description for business {business_id}")
                return False

        # Step 3: Enhance and translate
        success = enhance_and_translate_description(business, languages)
        if not success:
            logger.error(f"Enhancement and translation failed for business {business_id}")
            return False

        # Step 4: Process additional translations
        success = translate_business_info(business, languages)
        if not success:
            logger.error(f"Business info translation failed for business {business_id}")
            return False

        # Step 5: Final validation
        if not validate_translations(business):
            logger.error(f"Final validation failed for business {business_id}")
            return False

        # Update business status
        business.status = 'REVIEWED'
        business.save(update_fields=['status'])
        
        logger.info(f"Successfully completed all processes for business {business_id}")
        return True

    except Exception as e:
        logger.error(f"Error processing business {business_id}: {str(e)}", exc_info=True)
        return False

def generate_new_description(business):
    """
    Generates a new description for businesses with missing or invalid descriptions.
    """
    try:
        messages = [
            {
                "role": "system",
                "content": "You are an expert content writer specializing in business descriptions."
            },
            {
                "role": "user",
                "content": f"""
                Create a comprehensive business description with EXACTLY 220 words.
                Business: '{business.title}'
                Category: '{business.category_name}'
                Location: '{business.city}, {business.country}'

                Requirements:
                - EXACTLY 220 words
                - Include '{business.title}' in first paragraph
                - Use '{business.title}' exactly twice
                - 80% sentences under 20 words
                - Formal tone
                - SEO optimized
                - Avoid: 'vibrant', 'in the heart of', 'in summary'
                - Include specific details about services/offerings
                - Maintain professional language
                """
            }
        ]

        response = call_openai_with_retry(
            messages=messages,
            max_tokens=800,
            temperature=0.3
        )

        new_description = response['choices'][0]['message']['content'].strip()
        
        if new_description and len(new_description.split()) >= 200:
            business.description = new_description
            business.save(update_fields=['description'])
            logger.info(f"Successfully generated new description for business {business.id}")
            return True
        else:
            logger.error(f"Generated description for business {business.id} did not meet length requirements")
            return False

    except Exception as e:
        logger.error(f"Error generating new description for business {business.id}: {str(e)}", exc_info=True)
        return False

def monitor_translation_progress(business_id):
    """
    Monitors and logs the translation progress for a business.
    """
    try:
        business = Business.objects.get(id=business_id)
        total_fields = 6  # title, description in 3 languages
        completed_fields = sum(1 for field in [
            business.title, business.description,
            business.title_eng, business.description_eng,
            business.title_esp, business.description_esp
        ] if field and field.strip())

        progress = (completed_fields / total_fields) * 100
        logger.info(f"Translation progress for business {business_id}: {progress:.2f}%")
        
        return {
            'business_id': business_id,
            'progress': progress,
            'completed_fields': completed_fields,
            'total_fields': total_fields,
            'missing_fields': total_fields - completed_fields
        }

    except Exception as e:
        logger.error(f"Error monitoring translation progress for business {business_id}: {str(e)}", exc_info=True)
        return None

def batch_translate_similar(texts, target_language, batch_size=5):
    """
    Processes similar translations in batches to optimize API usage and maintain consistency.
    """
    results = []
    
    try:
        # Process texts in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Create a combined prompt for the batch
            combined_prompt = "\n===\n".join([
                f"Text {idx + 1}:\n{text}" 
                for idx, text in enumerate(batch)
            ])
            
            messages = [
                {
                    "role": "system",
                    "content": f"Translate the following texts to {target_language}. Maintain the original format and numbering."
                },
                {
                    "role": "user",
                    "content": combined_prompt
                }
            ]
            
            response = call_openai_with_retry(
                messages=messages,
                max_tokens=sum(len(text.split()) for text in batch) * 2,
                temperature=0.3
            )
            
            # Parse the batch response
            translated_batch = parse_batch_translations(
                response['choices'][0]['message']['content'],
                len(batch)
            )
            
            results.extend(translated_batch)
            
            # Add delay between batches
            time.sleep(1)
            
        return results
        
    except Exception as e:
        logger.error(f"Error in batch translation: {str(e)}", exc_info=True)
        return []

def parse_batch_translations(response_text, expected_count):
    """
    Parses the batch translation response into individual translations.
    """
    try:
        # Split by the separator we defined
        parts = response_text.split("===")
        
        # Clean and validate each part
        translations = []
        for part in parts:
            # Remove "Text N:" prefix and clean whitespace
            cleaned = re.sub(r'^Text \d+:', '', part, flags=re.MULTILINE).strip()
            if cleaned:
                translations.append(cleaned)
        
        # Validate we got the expected number of translations
        if len(translations) != expected_count:
            logger.warning(f"Expected {expected_count} translations but got {len(translations)}")
            
        return translations
        
    except Exception as e:
        logger.error(f"Error parsing batch translations: {str(e)}", exc_info=True)
        return []

def clean_and_validate_text(text, field_name, business_id):
    """
    Cleans and validates text content before processing.
    """
    if not text:
        logger.warning(f"Empty {field_name} for business {business_id}")
        return None
        
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove unwanted characters
    text = re.sub(r'[^\w\s.,!?;:()\-\'\"]+', ' ', text)
    
    # Validate minimum length
    if len(text.split()) < 3:
        logger.warning(f"Too short {field_name} for business {business_id}: {text}")
        return None
        
    return text

def update_translation_status(business, success=True):
    """
    Updates the translation status and logs the outcome.
    """
    try:
        if success:
            business.translation_status = 'TRANSLATED'
            logger.info(f"Translation completed successfully for business {business.id}")
        else:
            business.translation_status = 'FAILED'
            logger.error(f"Translation failed for business {business.id}")
            
        business.translation_updated_at = timezone.now()
        business.save(update_fields=['translation_status', 'translation_updated_at'])
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating translation status for business {business.id}: {str(e)}", exc_info=True)
        return False

def log_translation_metrics(business_id, start_time):
    """
    Logs metrics about the translation process.
    """
    try:
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"""
            Translation Metrics for Business {business_id}:
            Duration: {duration:.2f} seconds
            Timestamp: {timezone.now().isoformat()}
        """)
        
        # Store metrics in database if needed
        TranslationMetrics.objects.create(
            business_id=business_id,
            duration=duration,
            timestamp=timezone.now()
        )
        
    except Exception as e:
        logger.error(f"Error logging translation metrics: {str(e)}", exc_info=True)

class TranslationMetrics(models.Model):
    """
    Model to store translation metrics.
    """
    business = models.ForeignKey('Business', on_delete=models.CASCADE)
    duration = models.FloatField()
    timestamp = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['business', 'timestamp'])
        ]
 
#####################DESCRIPTION TRANSLATE##################################
 
def get_postal_code_pattern(country: str) -> Optional[str]:
        patterns = {
        'spain': r'\b\d{5}\b',
        'portugal': r'\b\d{4}(?:-\d{3})?\b',
        'france': r'\b\d{5}\b',
        'germany': r'\b\d{5}\b',
        'italy': r'\b\d{5}\b',
        'uk': r'\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b', 
        'united kingdom': r'\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b', 
        'ireland': r'\b[A-Z]\d{2} ?[A-Z\d]{4}\b',

        'usa': r'\b\d{5}(?:-\d{4})?\b',
        'united states of america': r'\b\d{5}(?:-\d{4})?\b',
        'us': r'\b\d{5}(?:-\d{4})?\b',
        'canada': r'\b[A-Z]\d[A-Z] ?\d[A-Z]\d\b', 

        'australia': r'\b\d{4}\b',
        'new zealand': r'\b\d{4}\b',
        'japan': r'\b\d{3}-?\d{4}\b',
        'china': r'\b\d{6}\b',
        'india': r'\b\d{6}\b',
        'singapore': r'\b\d{6}\b',
        'belgium': r'\b\d{4}\b',

        'default': r'\b\d{5}\b'
    }
        return patterns.get(country.lower(), patterns['default'])
 
def extract_address_components(address_string: string, country: str = None):
    """
    Extract address components from a full address string with country-specific postal code formats.
    
    Args:
        address_string: Full address string
        country: Country name to determine postal code format (optional)
    
    Returns:
        Dictionary with street_address and postal_code
    
    Example: 
        "Carrer del Call, 17, Ciutat Vella, 08002 Barcelona, Spain"
        "Rua Augusta 12, 1100-053 Lisboa, Portugal"
    """
    components = {
        'street_address': '',
        'postal_code': '',
        'country': country
    }
    
    if not address_string:
        return components

    try:
        address_string = address_string.strip()

        if not country:
            country_match = re.search(r',\s*([^,]+)$', address_string)
            if country_match:
                country = country_match.group(1).strip()
                components['country'] = country
        
        postal_pattern = get_postal_code_pattern(country) if country else get_postal_code_pattern('default')

        postal_code_match = re.search(postal_pattern, address_string)
        
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
        logger.info(f"Country detected: {components['country']}")
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

        # Create or update the business FIRST
        business, created = Business.objects.update_or_create(
            place_id=business_data['place_id'],
            defaults=business_data
        )

        if created:
            logger.info(f"New business created: {business.title} (ID: {business.id})")
        else:
            logger.info(f"Existing business updated: {business.title} (ID: {business.id})")

        # THEN save popular times
        popular_times_data = local_result.get('popular_times')  
        if popular_times_data:
            save_popular_times(business, popular_times_data)

        # Save categories
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

        # Save service options
        service_options = local_result.get('serviceOptions', {})
        if service_options:
            business.service_options = service_options
            business.save()

        logger.info(f"All business data processed and saved for business {business.id}")
        logger.info(f"Address components saved - Street: {business.street}, "
            f"Postal Code: {business.postal_code}, City: {business.city}")

        # Download images
        try:
            image_paths = download_images(business, local_result)
            logger.info(f"Downloaded {len(image_paths)} images for business {business.id}")
        except Exception as e:
            logger.error(f"Error downloading images for business {business.id}: {str(e)}", exc_info=True)

        return business

    except Exception as e:
        logger.error(f"Error saving business data for task {task.id}: {str(e)}", exc_info=True)
        raise

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

    def normalize_24hour_time(hour, minute, period):
        """Convert time to normalized 24-hour format"""
        if period:
            if period.upper() == 'PM' and hour != 12:
                hour += 12
            elif period.upper() == 'AM' and hour == 12:
                hour = 0
        return hour, minute

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
            
            # Use normalize_24hour_time to convert times
            start_hour, start_minute = normalize_24hour_time(start_hour, start_minute, start_period)
            end_hour, end_minute = normalize_24hour_time(end_hour, end_minute, end_period)
            
            # Convert to minutes for easier comparison
            start_minutes = start_hour * 60 + start_minute
            end_minutes = end_hour * 60 + end_minute
            
            # Handle after-midnight times
            if end_minutes <= start_minutes:
                end_minutes += 24 * 60  # Add 24 hours worth of minutes
            
            # Convert back to hours and minutes
            def from_minutes(minutes):
                # Handle wrapped time
                while minutes >= 24 * 60:
                    minutes -= 24 * 60
                    
                hour = minutes // 60
                minute = minutes % 60
                
                # Convert to 12-hour format
                period = 'AM'
                if hour >= 12:
                    period = 'PM'
                    if hour > 12:
                        hour -= 12
                elif hour == 0:
                    hour = 12
                
                return f"{hour:02d}:{minute:02d} {period}"
            
            formatted_start = from_minutes(start_minutes)
            
            # For end time at midnight, explicitly set it to 11:59 PM
            if end_minutes % (24 * 60) == 0 or (end_hour == 0 and end_minute == 0):
                formatted_end = "11:59 PM"
            else:
                formatted_end = from_minutes(end_minutes)
            
            return f"{formatted_start} – {formatted_end}"
            
        except Exception as e:
            logger.error(f"Error formatting single range '{time_range}': {str(e)}")
            return 'No hours specified'

    
    try:
        formatted_hours = {}
        
        if isinstance(operating_hours, dict):
            for day, hours in operating_hours.items():
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


###Busyness####

def save_popular_times(business, popular_times_data):
    if not popular_times_data or 'graph_results' not in popular_times_data:
        return

    graph_results = popular_times_data['graph_results']
    live_hash = popular_times_data.get('live_hash', {})

    for day, hours_data in graph_results.items():
        popular_times, created = PopularTimes.objects.get_or_create(
            business=business,
            day=day,
            defaults={
                'live_busyness_info': live_hash.get('info'),
                'time_spent': live_hash.get('time_spent')
            }
        )
        for hour_data in hours_data:
            HourlyBusyness.objects.update_or_create(
                popular_times=popular_times,
                time=hour_data['time'],
                defaults={
                    'busyness_score': hour_data.get('busyness_score', 0),
                    'info': hour_data.get('info', '')
                }
            )
