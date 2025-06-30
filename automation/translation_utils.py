import asyncio
import os
from typing import List, Dict, Optional
from django.core.cache import cache
import logging
import openai
import time
from functools import wraps
import json

logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv('GENAI_OPENAI_API_KEY')
CACHE_TIMEOUT = 86400  # 24 hours
MIN_WORDS = 220
MAX_RETRIES = 3
RETRY_DELAY = 1

openai.api_key = OPENAI_API_KEY

def retry_with_exponential_backoff(max_retries=MAX_RETRIES, initial_delay=RETRY_DELAY):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Final retry failed: {str(e)}", exc_info=True)
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

async def call_openai_with_retry(messages: List[Dict], model="gpt-3.5-turbo", temperature=0.7):
    """Make OpenAI API call with retry logic"""
    response = await openai.ChatCompletion.acreate(
        model=model,
        messages=messages,
        temperature=temperature
    )
    return response.choices[0].message.content.strip()

async def translate_text_openai(text: str, target_language: str) -> Optional[str]:
    """Translate text using OpenAI"""
    if not text:
        return None

    cache_key = f"trans_{hash(text)}_{target_language}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    messages = [
        {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_language}. Maintain the original meaning and tone."},
        {"role": "user", "content": text}
    ]

    try:
        translated_text = await call_openai_with_retry(messages)
        cache.set(cache_key, translated_text, CACHE_TIMEOUT)
        return translated_text
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        return None

async def generate_additional_sentences_openai(text: str, words_needed: int) -> str:
    """Generate additional sentences to meet minimum word count"""
    messages = [
        {"role": "system", "content": "You are a business description expert. Enhance the following text by adding more relevant details."},
        {"role": "user", "content": f"Enhance this business description by adding approximately {words_needed} more words while maintaining context and style: {text}"}
    ]

    try:
        enhanced_text = await call_openai_with_retry(messages, temperature=0.8)
        return enhanced_text
    except Exception as e:
        logger.error(f"Enhancement error: {str(e)}", exc_info=True)
        return text


def enhance_and_translate_description(business, languages=["spanish", "eng", "fr"]):
    """
    Enhances the business description and translates it into specified languages.
    Uses a single prompt to get both Spanish and English translations at once.
    Utilizing the improved call_openai_with_retry function.
    """
    if not business.description or not business.description.strip():
        logger.info(f"No base description available for business {business.id}. Enhancement and translation skipped.")
        return False

    try:
        # Prepare system and user prompts for enhancement
        enhance_messages = [
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
        ]

        response = call_openai_with_retry(enhance_messages, max_tokens=800)
        enhanced_description = response['choices'][0]['message']['content'].strip()
        business.description = enhanced_description

        if languages:
            # Single prompt for multiple translations
            combined_prompt = (
                "Translate the following text into both Spanish and British English. "
                "Provide both translations separated by [SPLIT]:\n\n"
                f"{enhanced_description}"
            )

            translation_messages = [
                {"role": "system", "content": "You are an expert multilingual translator."},
                {"role": "user", "content": combined_prompt}
            ]

            response_translations = call_openai_with_retry(translation_messages, max_tokens=1000)
            translations = response_translations['choices'][0]['message']['content'].split('[SPLIT]')

            if len(translations) >= 2:
                if "spanish" in languages:
                    business.description_esp = translations[0].strip()
                if "eng" in languages:
                    business.description_eng = translations[1].strip()
                if "fr" in languages:
                    try:
                        fr_translation = translate_text_openai(enhanced_description, 'French')
                        business.description_fr = fr_translation
                    except Exception as e:
                        logger.error(f"French translation failed: {str(e)}", exc_info=True)


        business.save()
        logger.info(f"Enhanced and translated description for business {business.id} into {', '.join(languages)}")
        return True

    except Exception as e:
        logger.error(f"Error processing business {business.id}: {str(e)}", exc_info=True)
        return False
 

async def translate_business_info(business) -> Dict:
    """Translate all business information"""
    logger.info(f"Starting translation for business {business.id}")
    results = {
        'success': True,
        'translations': {},
        'errors': []
    }

    try:
        # Translate and enhance description
        if business.description:
            desc_results = await enhance_and_translate_description(business.description)
            business.description = desc_results['original']
            business.description_esp = desc_results['translations'].get('description_esp')
            business.description_eng = desc_results['translations'].get('description_eng')
            business.description_fr = desc_results['translations'].get('description_fr')

        # Translate title
        if business.title:
            business.title_esp = await translate_text_openai(business.title, 'Spanish')
            business.title_eng = await translate_text_openai(business.title, 'English')
            business.title_fr = await translate_text_openai(business.title, 'French')

        await business.asave()
        logger.info(f"Translation completed for business {business.id}")

    except Exception as e:
        logger.error(f"Translation failed for business {business.id}: {str(e)}", exc_info=True)
        results['success'] = False
        results['errors'].append(str(e))

    return results

def translate_business_info_sync(business) -> Dict:
    """Synchronous wrapper for translate_business_info"""
    try:
        return asyncio.run(translate_business_info(business))
    except Exception as e:
        logger.error(f"Synchronous translation failed: {str(e)}", exc_info=True)
        return {
            'success': False,
            'errors': [str(e)]
        }

async def batch_translate_businesses(businesses: List) -> Dict:
    """Batch translate multiple businesses"""
    logger.info(f"Starting batch translation for {len(businesses)} businesses")
    results = {
        'total': len(businesses),
        'successful': 0,
        'failed': 0,
        'details': []
    }

    for business in businesses:
        try:
            translation_result = await translate_business_info(business)
            if translation_result['success']:
                results['successful'] += 1
            else:
                results['failed'] += 1
            results['details'].append({
                'business_id': business.id,
                'success': translation_result['success'],
                'errors': translation_result['errors']
            })
        except Exception as e:
            results['failed'] += 1
            results['details'].append({
                'business_id': business.id,
                'success': False,
                'errors': [str(e)]
            })

    logger.info(f"Batch translation completed: {results['successful']} successful, {results['failed']} failed")
    return results
