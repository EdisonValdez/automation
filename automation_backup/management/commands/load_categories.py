import json
from django.core.management.base import BaseCommand
from automation.models import Category, Level

class Command(BaseCommand):
    help = 'Load categories and subcategories from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str)

    def handle(self, *args, **kwargs):
        json_file = kwargs['json_file']
        
        try:
            with open(json_file, 'r') as file:
                data = json.load(file)

                for level_data in data.get("levels", []):
                    level_title = level_data.get("title")
                    level, created = Level.objects.get_or_create(title=level_title)

                    for category_data in level_data.get("categories", []):
                        category_title = category_data.get("title")
                        category_value = category_title.lower().replace(" ", "_")  # Generate a value for category

                        # Create or get the Category object
                        category, created = Category.objects.get_or_create(
                            title=category_title,
                            defaults={'level': level, 'value': category_value}
                        )

                        # Add subcategories correctly by setting the parent field
                        for subcategory_data in category_data.get("subcategories", []):
                            subcategory_title = subcategory_data.get("title")
                            subcategory_value = subcategory_title.lower().replace(" ", "_")  # Generate a value for subcategory

                            # Create the subcategory, linking it to the parent category
                            Category.objects.get_or_create(
                                title=subcategory_title,
                                defaults={'level': level, 'parent': category, 'value': subcategory_value}
                            )

                self.stdout.write(self.style.SUCCESS('Successfully loaded categories and subcategories'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error loading categories: {str(e)}'))
# python manage.py load_categories automation/level_categories/transportation.json
# python manage.py load_categories automation/level_categories/where_to_buy.json 
# python manage.py load_categories automation/level_categories/what_to_do.json  
# python manage.py load_categories automation/level_categories/rental_services.json
# python manage.py load_categories automation/level_categories/food_and_drink.json 
# python manage.py load_categories automation/level_categories/categories.json   
#
#
#
#
#
#