from celery import shared_task
from django.utils import timezone
from .models import ScrapingTask, Business, Category, OpeningHours, AdditionalInfo, Image
from django.conf import settings 
import os
import time
import json
import logging
import requests
from serpapi import GoogleSearch
import json
from celery import shared_task
import requests
from .models import Category, ScrapingTask, Business, OpeningHours, AdditionalInfo, Image
from django.utils import timezone
from django.conf import settings
import os
import logging
from .translation_utils import translate_business_info_sync
from serpapi import GoogleSearch
import time
from PIL import Image as PILImage
from io import BytesIO
logger = logging.getLogger(__name__)

SERPAPI_KEY = settings.SERPAPI_KEY   

@shared_task
def process_scraping_task(task_id):
    logger.info(f"Starting scraping task {task_id}")
    try:
        task = ScrapingTask.objects.get(id=task_id)
    except ScrapingTask.DoesNotExist:
        logger.error(f"ScrapingTask with id {task_id} does not exist.")
        return

    task.status = 'IN_PROGRESS'
    task.save()

    try:
        queries = read_queries(task.file.path)
        logger.info(f"Total queries to process: {len(queries)}")

        for query in queries:
            try:
                logger.info(f"Processing query: {query}")

                params = {
                    "api_key": SERPAPI_KEY,
                    "engine": "google_maps",
                    "type": "search",
                    "google_domain": "google.com",
                    "q": query,
                    "hl": "en",
                    "no_cache": "true"
                }

                search = GoogleSearch(params)
                results = search.get_dict()

                if 'error' in results:
                    logger.error(f"API Error for query '{query}': {results['error']}")
                    continue 

                # Save the results to a JSON file
                save_results(task, results, query)

                for local_result in results.get('local_results', []):
                    business = save_business(task, local_result, query)
                    download_images(business, local_result)

                time.sleep(2)  # To avoid overloading the API

            except Exception as e:
                logger.error(f"Error processing query '{query}': {str(e)}", exc_info=True)
                continue  # Continue with the next query

        logger.info(f"Scraping task {task_id} completed successfully")
        task.status = 'COMPLETED'
        task.completed_at = timezone.now()
        task.save()

    except Exception as e:
        logger.error(f"Error in scraping task {task_id}: {str(e)}", exc_info=True)
        task.status = 'FAILED'
        task.save()
        raise e

 
def save_business(task, local_result, query):
    logger.info(f"Saving business data for task {task.id}")
    try:
        business = Business.objects.create(
            task=task,
            search_string=query,   
            rank=local_result.get('rank', 0),
            search_page_url=local_result.get('searchPageUrl', ''),
            is_advertisement=local_result.get('isAdvertisement', False),
            title=local_result.get('title', ''),
            description=local_result.get('description', ''),
            price=local_result.get('price', ''),
            category_name=local_result.get('categoryName', ''),
            address=local_result.get('address', ''),
            neighborhood=local_result.get('neighborhood', ''),
            street=local_result.get('street', ''),
            city=local_result.get('city', ''),
            postal_code=local_result.get('postalCode', ''),
            state=local_result.get('state', ''),
            country_code=local_result.get('countryCode', ''),
            phone=local_result.get('phone', ''),
            phone_unformatted=local_result.get('phoneUnformatted', ''),
            claim_this_business=local_result.get('claimThisBusiness', False),
            latitude=local_result.get('location', {}).get('lat', None),
            longitude=local_result.get('location', {}).get('lng', None),
            total_score=local_result.get('totalScore', None),
            permanently_closed=local_result.get('permanentlyClosed', False),
            temporarily_closed=local_result.get('temporarilyClosed', False),
            place_id=local_result.get('placeId', ''),
            fid=local_result.get('fid', ''),
            cid=local_result.get('cid', ''),
            reviews_count=local_result.get('reviewsCount', None),
            images_count=local_result.get('imagesCount', None),
            scraped_at=timezone.now(),
            reserve_table_url=local_result.get('reserveTableUrl', None),
            google_food_url=local_result.get('googleFoodUrl', None),
            url=local_result.get('url', ''),
            image_url=local_result.get('imageUrl', None),
            project_id=task.project_id,
            project_title=task.project_title,
            main_category=task.main_category,
            tailored_category=task.tailored_category
        )
        logger.info(f"Business.objects.create {business.project_title}")

        # Save categories
        for category in local_result.get('categories', []):
            Category.objects.create(business=business, name=category)

        # Save opening hours
        for day_hours in local_result.get('openingHours', []):
            OpeningHours.objects.create(
                business=business,
                day=day_hours.get('day', ''),
                hours=day_hours.get('hours', '')
            )

        # Save additional info
        for category, items in local_result.get('additionalInfo', {}).items():
            for item in items:
                for key, value in item.items():
                    AdditionalInfo.objects.create(
                        business=business,
                        category=category,
                        key=key,
                        value=value
                    )

        logger.info(f"Business data saved successfully for task {task.id}")
        
        translate_business.delay(business.id)
        

         

        return business
    except Exception as e:
        logger.error(f"Error saving business data for task {task.id}: {str(e)}", exc_info=True)
        raise

def download_images(business, local_result):
    photos_link = local_result.get('photos_link')
    if not photos_link:
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

        for i, photo in enumerate(photos_results.get('photos', [])):
            image_url = photo.get('image')
            if image_url:
                try:
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        # Open the image using Pillow
                        img = PILImage.open(BytesIO(response.content))

                        # Calculate the aspect ratio
                        aspect_ratio = 3 / 2  # 3:2 aspect ratio

                        # Calculate new dimensions
                        if img.width / img.height > aspect_ratio:
                            # Image is wider than 3:2
                            new_width = int(img.height * aspect_ratio)
                            new_height = img.height
                        else:
                            # Image is taller than 3:2
                            new_width = img.width
                            new_height = int(img.width / aspect_ratio)

                        # Crop the image to 3:2
                        left = (img.width - new_width) / 2
                        top = (img.height - new_height) / 2
                        right = (img.width + new_width) / 2
                        bottom = (img.height + new_height) / 2
                        img_cropped = img.crop((left, top, right, bottom))

                        # Save the cropped image
                        file_name = f"image_{i+1}.jpg"
                        file_path = os.path.join(output_dir, file_name)
                        img_cropped.save(file_path, 'JPEG', quality=85)
                        with open(file_path, 'wb') as file:
                                file.write(response.content)

                        local_path = os.path.join('business_images', str(business.id), file_name)
                        Image.objects.create(
                            business=business,
                            image_url=image_url,
                            local_path=local_path
                        )

                    else:
                        logger.error(f"Failed to download image {i+1}: HTTP {response.status_code}")
                except Exception as e:
                    logger.error(f"Error downloading image {i+1}: {str(e)}", exc_info=True)

            time.sleep(1)  # To avoid overloading the server

    except Exception as e:
        logger.error(f"Error in download_images: {str(e)}", exc_info=True)

def read_queries(file_path):
    logger.info(f"Reading queries from file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        queries = [line.strip() for line in file if line.strip()]
    logger.info(f"Read {len(queries)} queries from file")
    return queries

@shared_task
def translate_business(business_id):
    logger.info(f"Starting translation for business {business_id}")
    try:
        business = Business.objects.get(id=business_id)
        translate_business_info_sync(business)
        logger.info(f"Translation completed for business {business_id}")
    except Business.DoesNotExist:
        logger.error(f"Business with id {business_id} not found")
    except Exception as e:
        logger.error(f"Error translating business {business_id}: {str(e)}", exc_info=True)


def save_results(task, results, query):
    output_dir = os.path.join(settings.MEDIA_ROOT, 'scraping_results', str(task.id))
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{query.replace(' ', '_')}.json"
    file_path = os.path.join(output_dir, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to {file_path}")
 