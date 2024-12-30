

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
        "spanish": "Spanish",
        "fr": "French",
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
                Google Types: '{business.types}'

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
 
        translations_status = {
            'spanish': False,
            'fr': False
        }

        if "spanish" in languages:
            try:
                spanish_messages = [
                    {"role": "system", "content": "You are an expert Spanish translator."},
                    {"role": "user", "content": f"""
                        Translate this text to Spanish, maintaining:
                        1. Formal tone and marketing style
                        2. Original text length and structure
                        3. All business-specific terms
                        4. SEO optimization

                        Text to translate:
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
                
                # Validate translation
                if len(spanish_description.split()) >= len(us_description.split()) * 0.8:
                    business.description_esp = spanish_description
                    translations_status['spanish'] = True
                    logger.info(f"Successfully translated to Spanish for business {business.id}")
                else:
                    logger.warning(f"Spanish translation length validation failed for business {business.id}")
                    
            except Exception as e:
                logger.error(f"Spanish translation failed for business {business.id}: {str(e)}", exc_info=True)

        if "fr" in languages:
            try:
                fr_messages = [
                    {"role": "system", "content": "You are an expert French translator."},
                    {"role": "user", "content": f"""
                        Translate this text to French, maintaining:
                        1. Formal tone and marketing style
                        2. Original text length and structure
                        3. All business-specific terms
                        4. SEO optimization

                        Text to translate:
                        {us_description}
                    """}
                ]

                fr_response = call_openai_with_retry(
                    messages=fr_messages,
                    model="gpt-3.5-turbo",
                    max_tokens=800,
                    temperature=0.3
                )

                fr_description = fr_response['choices'][0]['message']['content'].strip()
                
                # Validate translation
                if len(fr_description.split()) >= len(us_description.split()) * 0.8:
                    business.description_fr = fr_description
                    translations_status['fr'] = True
                    logger.info(f"Successfully translated to French for business {business.id}")
                else:
                    logger.warning(f"French translation length validation failed for business {business.id}")

            except Exception as e:
                logger.error(f"French translation failed for business {business.id}: {str(e)}", exc_info=True)

        # Save only if at least one translation was successful
        if any(translations_status.values()) or business.description_eng:
            business.save()
            logger.info(f"Successfully saved translations for business {business.id}")
            return True
        else:
            logger.error(f"No successful translations for business {business.id}")
            return False

    except Exception as e:
        logger.error(f"Error in enhance_and_translate_description for business {business.id}: {str(e)}", exc_info=True)
        return False

def generate_additional_sentences(business, word_deficit):
    """
    Generates additional sentences to meet the required word count.
    """
    if word_deficit <= 0:
        logger.debug(f"No additional words needed for business {business.id}")
        return ""

    try:
        prompt = (
            f"Generate additional content of exactly {word_deficit} words to describe:\n"
            f"'{business.title}', a '{business.category_name}' located in '{business.city}, {business.country}'.\n"
            f"Focus on its unique features, offerings, {business.types}, and appeal to customers.\n"
            f"Maintain the same tone and style as the existing description."
        )

        document = doctran.parse(content=prompt)
        additional_sentences = document.summarize(
            token_limit=word_deficit * 2
        ).transformed_content.strip()

        # Validate generated content
        if additional_sentences and len(additional_sentences.split()) >= word_deficit * 0.8:
            return additional_sentences
        else:
            logger.warning(f"Generated content too short for business {business.id}")
            return ""

    except Exception as e:
        logger.error(f"Error generating additional sentences for business {business.id}: {str(e)}", exc_info=True)
        return ""
    
def translate_business_info(business, languages=["spanish", "eng", "fr"]):
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
        if business.title and (not business.title_eng or not business.title_esp or not business.title_fr):
            success = translate_business_titles(business, languages)
            if not success:
                logger.error(f"Failed to translate titles for business {business.id}")
                return False
        
        # Case 3: Process types translations if needed
        if business.types and (not business.types_eng or not business.types_esp or not business.types_fr):
            success = translate_business_types(business, languages)
            if not success:
                logger.error(f"Failed to translate titles for business {business.id}")
                return False
            

        # Case 4: Process description translations
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
    
    if not business.types:
        logger.error(f"Business {business.id} missing tags or google types")
        return False
    
    if not business.description and not business.description_eng and not business.description_esp and not business.description_fr:
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
            
            elif lang == "fr" and not business.title_fr:
                translated_title = translate_text_openai(business.title, "fr")
                if translated_title:
                    business.title_fr = translated_title

        business.save(update_fields=['title_esp', 'title_eng', 'title_fr'])
        return True

    except Exception as e:
        logger.error(f"Error translating titles for business {business.id}: {str(e)}", exc_info=True)
        return False

def translate_business_types(business, languages):
    """
    Handles the translation of business tags and types.
    """
    try:
        for lang in languages:
            if lang == "spanish" and not business.types_esp:
                translated_types = translate_text_openai(business.types, "spanish")
                if translated_types:
                    business.types_esp = translated_types
                    
            elif lang == "eng" and not business.types_eng:
                translated_types = translate_text_openai(business.types, "eng")
                if translated_types:
                    business.types_eng = translated_types
            
            elif lang == "fr" and not business.types_fr:
                translated_types = translate_text_openai(business.types, "fr")
                if translated_types:
                    business.types_fr = translated_types

        business.save(update_fields=['types_esp', 'types_eng', 'types_fr'])
        return True

    except Exception as e:
        logger.error(f"Error translating types for business {business.id}: {str(e)}", exc_info=True)
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
            elif lang == "fr" and not business.description_fr:
                translated_desc = translate_text_openai(business.description, "fr")
                if translated_desc:
                    business.description_fr = translated_desc

        business.save(update_fields=['description_esp', 'description_eng', 'description_fr'])
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
        'title_eng': business.title_eng,
        'title_esp': business.title_esp,
        'title_fr': business.title_fr,
        'description': business.description,
        'description_eng': business.description_eng,
        'description_esp': business.description_esp,
        'description_fr': business.description_fr,
        'types': business.types,
        'types_eng': business.types_eng,
        'types_esp': business.types_esp,
        'types_fr': business.types_fr,
    }

    invalid_fields = []
    for field, value in required_fields.items():
        if not value or value.lower() in ['no description', 'none', '']:
            invalid_fields.append(field)

    if invalid_fields:
        logger.error(f"Business {business.id} missing or invalid fields: {', '.join(invalid_fields)}")
        return False

    return True

def enhance_translate_and_summarize_business(business_id, languages=["spanish", "eng", "fr"]):
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
                Google Types or tags: '{business.types}'
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
            model="gpt-3.5-turbo",
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
        total_fields = 12  
        completed_fields = sum(1 for field in [
            business.title, business.description, business.types,
            business.title_eng, business.description_eng, business.types_eng,
            business.title_esp, business.description_esp, business.types_esp,
            business.title_fr, business.description_fr, business.types_fr,
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
