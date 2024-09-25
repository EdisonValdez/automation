import asyncio
from doctran import Doctran
from langchain_community.document_transformers import DoctranTextTranslator
from langchain_core.documents import Document
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

#TRANSLATION_OPENAI_API_KEY="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"  #Translation Local Secret
doctran = Doctran(openai_api_key=settings.TRANSLATION_OPENAI_API_KEY, openai_model="gpt-3.5-turbo-instruct")
#doctran = Doctran(openai_api_key=TRANSLATION_OPENAI_API_KEY, openai_model="gpt-3.5-turbo-instruct")

async def translate_text(text, target_language):
    logger.info(f"Translating text to {target_language}")
    try:
        translator = DoctranTextTranslator(language=target_language, openai_api_key=settings.OPENAI_API_KEY, openai_api_model="gpt-3.5-turbo-instruct")
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
    business.title_fr = await translate_text(business.title, "french")
    # Translate description
    if business.description:
        business.description_esp = await translate_text(business.description, "spanish")
        business.description_fr = await translate_text(business.description, "french")

    business.save()
    logger.info(f"Completed translation for business {business.id}")


def translate_business_info_sync(business):
    logger.info(f"Starting synchronous translation for business {business.id}")
    try:
        asyncio.run(translate_business_info(business))
        logger.info(f"Completed synchronous translation for business {business.id}")
    except Exception as e:
        logger.error(f"Error in synchronous translation for business {business.id}: {str(e)}", exc_info=True)

