from datetime import datetime
import logging
from django.core.exceptions import ValidationError
from automation.models import Country, Level, Category, Destination

logger = logging.getLogger(__name__)


def datetime_serializer(obj):
    """Recursively convert datetime objects to ISO format"""

    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class DataSyncer:
    """
    Initialize the DataSyncer with the data coming from LS backend, 
    preparing it to move records to the automation system.
    """

    def __init__(self, request):
        self.request_data = request.POST

    def get_country(self, country_lsid: int) -> Country:
        """"
        Checks if the country already exists. If it does, it returns the existing country.
        If the country doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            self.country, _ = Country.objects.get_or_create(
                ls_id=country_lsid,
                defaults={
                    'name': self.request_data.get('country_name'),
                    'code': self.request_data.get('country_code'),
                    'phone_code': self.request_data.get('country_phone_code'),
                }
            )
            return self.country
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the country: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the country. Please check the provided data.")

    def get_destination(self, city_lsid: int) -> Destination:
        """"
        Checks if the destination already exists. If it does, it returns the existing destination.
        If the destination doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            self.destination, _ = Destination.objects.get_or_create(
                ls_id=city_lsid,
                country=self.country.id,
                defaults={
                    'name': self.request_data.get('city_name'),
                    'cp': self.request_data.get('city_cp'),
                    'province': self.request_data.get('city_province'),
                    'description': self.request_data.get('city_description'),
                    'link': self.request_data.get('city_link'),
                    'latitude': self.request_data.get('city_latitude'),
                    'longitude': self.request_data.get('city_longitude'),
                    'country': self.country,
                }
            )
            return self.destination
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the destination: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the destination. Please check the provided data.")

    def get_level(self, level_lsid: int) -> Level:
        """"
        Checks if the level already exists. If it does, it returns the existing level.
        If the level doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            self.level, _ = Level.objects.get_or_create(
                ls_id=level_lsid,
                defaults={
                    'title': self.request_data.get('level_name')
                }
            )
            return self.level
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the level: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the level. Please check the provided data.")

    def get_category(self, category_lsid: int) -> Category:
        """"
        Checks if the category already exists. If it does, it returns the existing category.
        If the category doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            self.category, _ = Category.objects.get_or_create(
                ls_id=category_lsid,
                level=self.level.id,
                defaults={
                    'title': self.request_data.get('category_name'),
                    'value': self.request_data.get('category_name'),
                    'level': self.level
                }
            )
            return self.category
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the category: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the category. Please check the provided data.")

    def get_subcategory(self, subcategory_lsid) -> Category:
        """"
        Checks if the subcategory already exists. If it does, it returns the existing subcategory.
        If the subcategory doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            self.subcategory, _ = Category.objects.get_or_create(
                ls_id=int(subcategory_lsid),
                parent=self.category.id,
                level=self.level.id,
                defaults={
                    'title': self.request_data.get('sub_category_name'),
                    'value': self.request_data.get('sub_category_name'),
                    'parent': self.category,
                    'level': self.level
                }
            )
            return self.subcategory
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the subcategory: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the subcategory. Please check the provided data.")

    def sync(self):
        """
        Orchestrates the data synchronization process for country, destination, level, category, subcategory.
        """
        country_ls_id = int(self.request_data.get('country'))
        destination_ls_id = int(self.request_data.get('destination'))
        level_ls_id = int(self.request_data.get('level'))
        category_ls_id = int(self.request_data.get('main_category'))
        sub_category_ls_id = self.request_data.get('subcategory')

        return {
            "country": self.get_country(country_ls_id),
            "destination": self.get_destination(destination_ls_id),
            "level": self.get_level(level_ls_id),
            "category": self.get_category(category_ls_id),
            "subcategory": self.get_subcategory(int(sub_category_ls_id)) if sub_category_ls_id else None,
        }
