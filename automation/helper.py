from datetime import datetime
import logging
from django.core.exceptions import ValidationError
from django.db.models import Q
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

    def _get_country(self, country_lsid: int) -> Country:
        """"
        Checks if the country already exists. If it does, it returns the existing country.
        If the country doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            country_name = self.request_data.get('country_name')
            self.country = Country.objects.filter(
                Q(ls_id=country_lsid) |
                Q(name__iexact=country_name)).last()

            if not self.country:
                self.country = Country.objects.create(
                    ls_id=country_lsid,
                    name=country_name,
                    code=self.request_data.get('country_code'),
                    phone_code=self.request_data.get('country_phone_code')
                )
            return self.country
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the country: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the country. Please check the provided data.")

    def _get_destination(self, city_lsid: int) -> Destination:
        """"
        Checks if the destination already exists. If it does, it returns the existing destination.
        If the destination doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            city_name = self.request_data.get("city_name")
            self.destination = (
                Destination.objects.filter(
                    Q(ls_id=city_lsid) |
                    (
                        Q(name__iexact=city_name) &
                        Q(country=self.country.id)
                    )).last())

            if not self.destination:
                self.destination = Destination.objects.create(
                    ls_id=city_lsid,
                    name=city_name,
                    cp=self.request_data.get('city_cp'),
                    province=self.request_data.get('city_province'),
                    description=self.request_data.get('city_description'),
                    link=self.request_data.get('city_link'),
                    latitude=self.request_data.get('city_latitude'),
                    longitude=self.request_data.get('city_longitude'),
                    country=self.country
                )
            return self.destination
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the destination: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the destination. Please check the provided data.")

    def _get_level(self, level_lsid: int) -> Level:
        """"
        Checks if the level already exists. If it does, it returns the existing level.
        If the level doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            level_name = self.request_data.get('level_name')
            self.level = Level.objects.filter(
                Q(ls_id=level_lsid) |
                Q(title__iexact=level_name)).last()

            if not self.level:
                self.level = Level.objects.create(
                    ls_id=level_lsid,
                    title=level_name
                )
            return self.level
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the level: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the level. Please check the provided data.")

    def _get_category(self, category_lsid: int) -> Category:
        """"
        Checks if the category already exists. If it does, it returns the existing category.
        If the category doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            category_name = self.request_data.get('category_name')
            self.category = Category.objects.filter(Q(parent__isnull=True) & (
                Q(ls_id=category_lsid) | (Q(title__iexact=category_name) & Q(level=self.level.id)))).last()

            if not self.category:
                self.category = Category.objects.create(
                    ls_id=category_lsid,
                    title=category_name,
                    value=category_name,
                    level=self.level
                )
            return self.category
        except Exception as e:
            logger.error(
                f"Failed to retrieve or create the category: {str(e)}",
                exc_info=True)
            raise ValidationError(
                "Failed to retrieve or create the category. Please check the provided data.")

    def _get_subcategory(self, subcategory_lsid) -> Category:
        """"
        Checks if the subcategory already exists. If it does, it returns the existing subcategory.
        If the subcategory doesn't exist, it creates a new one and returns the newly created object.
        """
        try:
            self.subcategory, _ = Category.objects.get_or_create(
                ls_id=subcategory_lsid,
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

    def _validate_fields(self):
        """Validate country, destination, level and main category
        """
        errors = {}

        if not (self.request_data.get('country')):
            errors["country"] = ["Please select a country."]

        if not (self.request_data.get('destination')):
            errors["destination"] = ["Please select a destination."]

        if not (self.request_data.get('level')):
            errors["level"] = ["Please select a level."]

        if not (self.request_data.get('main_category')):
            errors["main_category"] = ["Please select a main category."]

        if errors:
            raise ValidationError(errors)

    def sync(self):
        """
        Orchestrates the data synchronization process for country, destination, level, category, subcategory.
        """
        self._validate_fields()
        country_lsid = int(self.request_data.get('country'))
        city_lsid = int(self.request_data.get('destination'))
        level_lsid = int(self.request_data.get('level'))
        category_lsid = int(self.request_data.get('main_category'))
        subcategory_lsid = self.request_data.get('subcategory')

        return {
            "country": self._get_country(country_lsid),
            "destination": self._get_destination(city_lsid),
            "level": self._get_level(level_lsid),
            "category": self._get_category(category_lsid),
            "subcategory": self._get_subcategory(int(subcategory_lsid)) if subcategory_lsid else None,
        }
