import asyncio
import os
from doctran import Doctran
from langchain_community.document_transformers import DoctranTextTranslator
from langchain_core.documents import Document
from django.conf import settings
import logging

import openai
logger = logging.getLogger(__name__)

GENAI_OPENAI_API_KEY = os.getenv('GENAI_OPENAI_API_KEY')
TRANSLATION_OPENAI_API_KEY = os.getenv('GENAI_OPENAI_API_KEY')

openai.api_key = GENAI_OPENAI_API_KEY
 

doctran = Doctran(openai_api_key=TRANSLATION_OPENAI_API_KEY, openai_model="gpt-3.5-turbo-instruct")
 
async def translate_text(text, target_language):
    logger.info(f"Translating text to {target_language}")
    try:
        translator = DoctranTextTranslator(language=target_language, openai_api_key=GENAI_OPENAI_API_KEY, openai_api_model="gpt-3.5-turbo-instruct")
        document = Document(page_content=text)
        translated_docs = await translator.atransform_documents([document])
        logger.info(f"Text successfully translated to {target_language}")
        return translated_docs[0].page_content
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        print(f"Translation error: {str(e)}")
        return None

async def translate_business_info(business):
    logger.info(f"Starting translation for business {business.id}")
    # Translate title
    business.title_esp = await translate_text(business.title, "spanish")
    business.description_eng = await translate_text(business.description, "british")
    # Translate description
    if business.description:
        business.description_esp = await translate_text(business.description, "spanish")
        business.description_eng = await translate_text(business.description, "british")

    business.save()
    logger.info(f"Completed translation for business {business.id}")


def translate_business_info_sync(business):
    logger.info(f"Starting synchronous translation for business {business.id}")
    try:
        asyncio.run(translate_business_info(business))
        logger.info(f"Completed synchronous translation for business {business.id}")
    except Exception as e:
        logger.error(f"Error in synchronous translation for business {business.id}: {str(e)}", exc_info=True)

