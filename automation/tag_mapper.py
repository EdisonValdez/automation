# tag_mapper.py
from django.core.cache import cache
from typing import List, Dict, Union

import openai
from automation.models import TagMapping
import logging

logger = logging.getLogger(__name__)

class TagMappingService:
    def __init__(self):
        self._load_cache()
    
    def _load_cache(self):
        """Load existing tag mappings from cache or database"""
        self.cache = cache.get('tag_mappings')
        if not self.cache:
            mappings = TagMapping.objects.all().values(
                'english_tag', 'spanish_tag', 'french_tag'
            )
            self.cache = {
                m['english_tag'].lower(): {
                    'spanish': m['spanish_tag'],
                    'french': m['french_tag'],
                    'eng': m['english_tag']
                }
                for m in mappings
            }
            cache.set('tag_mappings', self.cache, timeout=3600)

    def process_business_types(self, scraped_types: Union[str, List[str]]) -> Dict[str, str]:
        """
        Process scraped types and return translations, creating new mappings if needed
        """
        # Normalize input to list
        if isinstance(scraped_types, str):
            types_list = [t.strip() for t in scraped_types.split(',') if t.strip()]
        elif isinstance(scraped_types, (list, tuple)):
            types_list = [t.strip() for t in scraped_types if t.strip()]
        else:
            logger.warning(f"Invalid type format: {type(scraped_types)}")
            return {'types': '', 'types_eng': '', 'types_esp': '', 'types_fr': ''}

        # Remove duplicates while preserving order
        types_list = list(dict.fromkeys(types_list))
        
        # Initialize result
        result = {
            'types': ', '.join(types_list),  # Original scraped types
            'types_eng': ', '.join(types_list),
            'types_esp': [],
            'types_fr': []
        }

        # Process each type
        new_mappings = []
        for type_str in types_list:
            normalized_type = type_str.lower().strip()
            
            # Check if type exists in cache
            if normalized_type in self.cache:
                # Use existing translations
                result['types_esp'].append(self.cache[normalized_type]['spanish'])
                result['types_fr'].append(self.cache[normalized_type]['french'])
            else:
                # Create new mapping
                try:
                    # Create new mapping in database
                    mapping = TagMapping.objects.create(
                        english_tag=type_str,
                        spanish_tag=self._translate_text(type_str, 'spanish'),
                        french_tag=self._translate_text(type_str, 'french')
                    )
                    
                    # Add to new mappings list
                    new_mappings.append({
                        'english_tag': mapping.english_tag,
                        'spanish_tag': mapping.spanish_tag,
                        'french_tag': mapping.french_tag
                    })
                    
                    # Add translations to result
                    result['types_esp'].append(mapping.spanish_tag)
                    result['types_fr'].append(mapping.french_tag)
                    
                except Exception as e:
                    logger.error(f"Error creating mapping for {type_str}: {str(e)}")
                    # Use original text as fallback
                    result['types_esp'].append(type_str)
                    result['types_fr'].append(type_str)

        # Update cache with new mappings
        if new_mappings:
            for mapping in new_mappings:
                self.cache[mapping['english_tag'].lower()] = {
                    'spanish': mapping['spanish_tag'],
                    'french': mapping['french_tag'],
                    'eng': mapping['english_tag']
                }
            cache.set('tag_mappings', self.cache, timeout=3600)

        # Convert lists to strings
        result['types_esp'] = ', '.join(result['types_esp'])
        result['types_fr'] = ', '.join(result['types_fr'])

        return result

    def _translate_text(self, text: str, target_lang: str) -> str:
        """
        Translate text using OpenAI service
        
        Args:
            text: Text to translate
            target_lang: Target language code ('spanish', 'french')
            
        Returns:
            Translated text or original text if translation fails
        """
        if not text.strip():
            return text

        lang_display = {
            'spanish': 'Spanish',
            'french': 'French'
        }

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator. "
                        f"Translate the following business type or category to {lang_display[target_lang]}. "
                        "Keep proper nouns unchanged. Use standard business terminology."
                    )
                },
                {"role": "user", "content": text}
            ]

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent translations
                max_tokens=100
            )

            translated_text = response.choices[0].message.content.strip()
            logger.info(f"Translated '{text}' to {target_lang}: '{translated_text}'")
            return translated_text

        except openai.error.RateLimitError:
            logger.error(f"OpenAI rate limit reached while translating: {text}")
            return text
        except Exception as e:
            logger.error(f"Translation error for text '{text}': {str(e)}")
            return text

 