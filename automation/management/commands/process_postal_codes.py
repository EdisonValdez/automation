# automation/management/commands/process_postal_codes.py 

from django.core.management.base import BaseCommand
from typing import List, Dict, Optional, Tuple

from django.db.models import Q, Count
from django.db import transaction
from automation.models import Business
from typing import Optional, Dict, List
import re
import logging
import openai
from time import sleep
from django.conf import settings

logger = logging.getLogger(__name__)

POSTAL_CODE_SETTINGS = {
    'GPT_BATCH_SIZE': 5,
    'BATCH_DELAY': 1,  # seconds
    'DEFAULT_STATUS': 'PENDING',
    'GPT_MAX_RETRIES': 3
}
 
class PostalCodeProcessor:      

    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.patterns = {
            # European Union Countries
            'austria': r'\b\d{4}\b',  # Format: 1010 (Vienna)
            'belgium': r'\b\d{4}\b',  # Format: 1000 (Brussels)
            'bulgaria': r'\b\d{4}\b',  # Format: 1000 (Sofia)
            'croatia': r'\b\d{5}\b',  # Format: 10000 (Zagreb)
            'cyprus': r'\b\d{4}\b',  # Format: 1000 (Nicosia)
            'czech republic': r'\b\d{3} ?\d{2}\b',  # Format: 100 00 (Prague)
            'denmark': r'\b\d{4}\b',  # Format: 1000 (Copenhagen)
            'estonia': r'\b\d{5}\b',  # Format: 10111 (Tallinn)
            'finland': r'\b\d{5}\b',  # Format: 00100 (Helsinki)
            'france': r'\b\d{5}\b',  # Format: 75001 (Paris)
            'germany': r'\b\d{5}\b',  # Format: 10115 (Berlin)
            'greece': r'\b\d{3} ?\d{2}\b',  # Format: 104 31 (Athens)
            'hungary': r'\b\d{4}\b',  # Format: 1011 (Budapest)
            'ireland': r'\b[A-Z]\d{2} ?[A-Z\d]{4}\b',  # Format: D02 AF30 (Dublin)
            'italy': r'\b\d{5}\b',  # Format: 00100 (Rome)
            'latvia': r'\b\d{4}\b',  # Format: 1050 (Riga)
            'lithuania': r'\b\d{5}\b',  # Format: 01001 (Vilnius)
            'luxembourg': r'\b\d{4}\b',  # Format: 1000
            'malta': r'\b[A-Z]{3} ?\d{4}\b',  # Format: VLT 1117
            'netherlands': r'\b\d{4} ?[A-Z]{2}\b',  # Format: 1000 AP
            'poland': r'\b\d{2}-\d{3}\b',  # Format: 00-001
            'portugal': r'\b\d{4}(?:-\d{3})?\b',  # Format: 1000-205
            'romania': r'\b\d{6}\b',  # Format: 010001
            'slovakia': r'\b\d{3} ?\d{2}\b',  # Format: 811 01
            'slovenia': r'\b\d{4}\b',  # Format: 1000
            'spain': r'\b\d{5}\b',  # Format: 28001
            'sweden': r'\b\d{3} ?\d{2}\b',  # Format: 100 00

            # Americas
            'argentina': r'\b[ABCEGHJLNPQRSTVWXY]\d{4}[A-Z]{3}\b',  # Format: C1425DKF
            'brazil': r'\b\d{5}-?\d{3}\b',  # Format: 01001-000
            'canada': r'\b[ABCEGHJKLMNPRSTVXY]\d[ABCEGHJKLMNPRSTVWXYZ] ?\d[ABCEGHJKLMNPRSTVWXYZ]\d\b',  # Format: A1A 1A1
            'chile': r'\b\d{7}\b',  # Format: 8320000
            'colombia': r'\b\d{6}\b',  # Format: 110111
            'costa rica': r'\b\d{5}(?:-\d{4})?\b',  # Format: 10101
            'mexico': r'\b\d{5}\b',  # Format: 01000
            'panama': r'\b\d{4}\b',  # Format: 0801
            'peru': r'\b\d{5}\b',  # Format: 15001
            'united states': r'\b\d{5}(?:-\d{4})?\b',  # Format: 10001 or 10001-1234
            'uruguay': r'\b\d{5}\b',  # Format: 11000
            'venezuela': r'\b\d{4}\b',  # Format: 1010

            # Asia
            'china': r'\b\d{6}\b',  # Format: 100000
            'hong kong': r'\b\d{6}\b',  # Format: 999077
            'india': r'\b\d{6}\b',  # Format: 110001
            'indonesia': r'\b\d{5}\b',  # Format: 10110
            'israel': r'\b\d{5}(?:\d{2})?\b',  # Format: 91000
            'japan': r'\b\d{3}-?\d{4}\b',  # Format: 100-0001
            'malaysia': r'\b\d{5}\b',  # Format: 50000
            'philippines': r'\b\d{4}\b',  # Format: 1000
            'russia': r'\b\d{6}\b',  # Format: 101000
            'singapore': r'\b\d{6}\b',  # Format: 238838
            'south korea': r'\b\d{5}\b',  # Format: 03154
            'taiwan': r'\b\d{3}(?:\d{2})?\b',  # Format: 100 or 10001
            'thailand': r'\b\d{5}\b',  # Format: 10200
            'vietnam': r'\b\d{6}\b',  # Format: 100000

            # Oceania
            'australia': r'\b\d{4}\b',  # Format: 2000
            'new zealand': r'\b\d{4}\b',  # Format: 0110

            # Africa
            'egypt': r'\b\d{5}\b',  # Format: 11511
            'morocco': r'\b\d{5}\b',  # Format: 10000
            'south africa': r'\b\d{4}\b',  # Format: 0083
            'tunisia': r'\b\d{4}\b',  # Format: 1000

            # Special Regions
            'sardinia': r'\b0[7-9]\d{3}\b',  # Format: 07100
            'sicily': r'\b9[0-5]\d{3}\b',  # Format: 90100
            
            # Default pattern for unknown countries
            'default': r'\b\d{5}\b'
        }

        self.city_defaults = {
            # Europe
            'athens': {
                'postal_code': '11743',
                'country': 'greece',
                'aliases': ['athina', 'athens', 'αθήνα'],
                'ranges': [(10431, 11523)],
                'valid_formats': [r'\b\d{5}\b']
            },
            'paris': {
                'postal_code': '75001',
                'country': 'france',
                'aliases': ['paris', 'parís'],
                'ranges': [(75001, 75020)],
                'valid_formats': [r'\b75\d{3}\b']
            },
            'london': {
                'postal_code': 'SW1A 1AA',
                'country': 'united kingdom',
                'aliases': ['london', 'londres'],
                'ranges': [],  # Complex system with letter-based codes
                'valid_formats': [r'\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b']
            },

            # Americas
            'san carlos de bariloche': {
                'postal_code': '8400',
                'province': 'Rio Negro',
                'country': 'argentina',
                'aliases': ['bariloche', 'san carlos de bariloche', 'scb'],
                'ranges': [(8400, 8400)],
                'valid_formats': [r'\b8400\b']
            },
            'new york': {
                'postal_code': '10001',
                'country': 'united states',
                'aliases': ['new york', 'nyc', 'nueva york'],
                'ranges': [(10001, 10292)],
                'valid_formats': [r'\b100\d{2}\b', r'\b102\d{2}\b']
            },
            'sao paulo': {
                'postal_code': '01000-000',
                'country': 'brazil',
                'aliases': ['sao paulo', 'são paulo'],
                'ranges': [(1000000, 5999999)],
                'valid_formats': [r'\b\d{5}-\d{3}\b']
            },

            # Asia
            'tokyo': {
                'postal_code': '100-0001',
                'country': 'japan',
                'aliases': ['tokyo', 'tokio', '東京'],
                'ranges': [(1000000, 2080035)],
                'valid_formats': [r'\b\d{3}-\d{4}\b']
            },
            'singapore': {
                'postal_code': '238838',
                'country': 'singapore',
                'aliases': ['singapore', 'singapura', '新加坡'],
                'ranges': [(10000, 899999)],
                'valid_formats': [r'\b\d{6}\b']
            }
        }

        self.country_ranges = {
            'argentina': {
                'ranges': [
                    (1000, 9999),  # General range
                    (1401, 1499),  # Buenos Aires
                    (8400, 8400),  # Bariloche
                    (9410, 9410)   # Ushuaia
                ],
                'default_format': r'\b[ABCEGHJLNPQRSTVWXY]\d{4}[A-Z]{3}\b'
            },
            'france': {
                'ranges': [
                    (75001, 75020),  # Paris
                    (13001, 13016),  # Marseille
                    (69001, 69009)   # Lyon
                ],
                'default_format': r'\b\d{5}\b'
            },
            'japan': {
                'ranges': [
                    (100, 999),    # Tokyo
                    (600, 699),    # Kyoto
                    (530, 539)     # Osaka
                ],
                'default_format': r'\b\d{3}-?\d{4}\b'
            },
            'united kingdom': {
                'regions': {
                    'london': ['E', 'EC', 'N', 'NW', 'SE', 'SW', 'W', 'WC'],
                    'manchester': ['M'],
                    'birmingham': ['B'],
                    'liverpool': ['L']
                },
                'default_format': r'\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b'
            },
            'united states': {
                'ranges': [
                    (10001, 10292),  # New York
                    (90001, 90089),  # Los Angeles
                    (60601, 60707)   # Chicago
                ],
                'default_format': r'\b\d{5}(?:-\d{4})?\b'
            },
            'china': {
                'ranges': [
                    (100000, 102629),  # Beijing
                    (200000, 202199),  # Shanghai
                    (510000, 510999)   # Guangzhou
                ],
                'default_format': r'\b\d{6}\b'
            }
        }
        
    def get_postal_code_pattern(self, country: str) -> Optional[str]:
        """Get regex pattern for country's postal codes"""
        return self.patterns.get(country.lower())

    def validate_postal_code(self, postal_code: str, country: str) -> bool:
        """Validate postal code format for country"""
        if not postal_code:
            return False
            
        pattern = self.get_postal_code_pattern(country)
        if not pattern:
            return True  # If no pattern exists, accept any format
        return bool(re.match(pattern, postal_code))

    def process_batch_with_gpt(self, businesses: List[Dict]) -> List[Tuple[int, str]]:
        """Process multiple businesses in a single GPT call"""
        try:
            # Build combined prompt
            prompts = []
            for business in businesses:
                prompts.append(self._build_gpt_prompt(business))
            
            combined_prompt = "\n---\n".join(prompts)
            
            # Call GPT-3.5 with combined prompt
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """You are a postal code expert. 
                    For each location separated by ---, return its postal code in the format:
                    ID|POSTAL_CODE|CONFIDENCE(HIGH/MEDIUM/LOW)
                    If you can't determine a postal code, return: ID|NONE|LOW
                    Respond with one result per line."""},
                    {"role": "user", "content": combined_prompt}
                ],
                temperature=0.1,
                max_tokens=100 * len(businesses)  # Scale tokens with batch size
            )
            
            # Process results
            results = []
            response_lines = response.choices[0].message.content.strip().split('\n')
            
            for line in response_lines:
                try:
                    business_id, postal_code, confidence = line.strip().split('|')
                    if postal_code.upper() != 'NONE' and confidence in ['HIGH', 'MEDIUM']:
                        results.append((int(business_id), postal_code))
                except ValueError:
                    logger.error(f"Invalid GPT response format: {line}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"GPT batch processing error: {str(e)}")
            return []
    def _build_gpt_prompt(self, business: Dict) -> str:
        """Build prompt for a single business"""
        components = [
            f"ID: {business['id']}",
            f"Location:",
            f"Address: {business['address']}",
            f"Street: {business['street']}",
            f"City: {business['city']}",
            f"Country: {business['country']}"
        ]
        
        if business['latitude'] and business['longitude']:
            components.append(
                f"Coordinates: {business['latitude']}, {business['longitude']}"
            )
            
        return "\n".join(components)
 
    def get_postal_code_via_gpt(self, business: Dict) -> Optional[str]:
        """Enhanced version with multiple fallback mechanisms"""
        try:
            # 1. First try to extract from existing address
            postal_code = self.extract_from_address(business['address'], business['country'])
            if postal_code:
                return self.validate_and_format_postal_code(postal_code, business)
            # 2. Try city defaults
            postal_code = self.get_city_default_postal_code(business)
            if postal_code:
                return postal_code
            # 3. Use GPT only if previous methods fail
            prompt = self._build_enhanced_gpt_prompt(business)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """You are a postal code expert. 
                    Given location details, return the postal code in the following format:
                    POSTAL_CODE|CONFIDENCE(HIGH/MEDIUM/LOW)|SOURCE(OFFICIAL/DERIVED)
                    If you can't determine the postal code, return: NONE|LOW|NONE"""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            postal_code, confidence, source = result.split('|')
            
            if postal_code.upper() == 'NONE':
                # 4. Final fallback to default ranges
                return self.get_default_postal_code(business)
                
            if confidence in ['HIGH', 'MEDIUM']:
                return self.validate_and_format_postal_code(postal_code, business)
            
            # If low confidence, try default
            return self.get_default_postal_code(business)
            
        except Exception as e:
            logger.error(f"GPT API error: {str(e)}")
            # 5. Emergency fallback
            return self.get_default_postal_code(business)
    
    def get_city_default_postal_code(self, business: Dict) -> Optional[str]:
        """Get default postal code for a city with fuzzy matching"""
        city_name = business['city'].lower()
        country = business['country'].lower()
        
        # Try direct match
        city_info = next(
            (info for key, info in self.city_defaults.items()
             if city_name in info['aliases'] and info['country'] == country),
            None
        )
        
        if city_info:
            return city_info['postal_code']
        
        return None
    
    def get_default_postal_code(self, business: Dict) -> Optional[str]:
        """Get a valid default postal code based on country/city"""
        country = business['country'].lower()
        city = business['city'].lower()
        
        # Try city defaults first
        for city_info in self.city_defaults.values():
            if (city in city_info['aliases'] and 
                city_info['country'] == country):
                return city_info['postal_code']
        
        # Fallback to country ranges
        if country in self.country_ranges:
            ranges = self.country_ranges[country]['ranges']
            if ranges:
                # Use first range as default
                start, end = ranges[0]
                return str(start)  # Use start of range as default
                
        return None
    
    def validate_and_format_postal_code(self, postal_code: str, business: Dict) -> Optional[str]:
        """Validate and format postal code according to country/city rules"""
        country = business['country'].lower()
        city = business['city'].lower()
        
        # Check city-specific format first
        city_info = next(
            (info for key, info in self.city_defaults.items()
             if city in info['aliases'] and info['country'] == country),
            None
        )
        
        if city_info:
            for pattern in city_info['valid_formats']:
                if re.match(pattern, postal_code):
                    return postal_code
        
        # Fall back to country pattern
        if self.validate_postal_code(postal_code, country):
            return postal_code
            
        return None
    
    def _build_enhanced_gpt_prompt(self, business: Dict) -> str:
        """Build an enhanced prompt with more context"""
        components = [
            f"Find the postal code for this location:",
            f"Address: {business['address']}",
            f"Street: {business['street']}",
            f"City: {business['city']}",
            f"Country: {business['country']}"
        ]
        
        # Add coordinates if available
        if business['latitude'] and business['longitude']:
            components.append(
                f"Coordinates: {business['latitude']}, {business['longitude']}"
            )
        
        # Add known postal code format if available
        country = business['country'].lower()
        if country in self.patterns:
            components.append(
                f"Expected format: {self.patterns[country]}"
            )
            
        # Add any city-specific information
        city_info = next(
            (info for key, info in self.city_defaults.items()
             if business['city'].lower() in info['aliases']),
            None
        )
        if city_info:
            components.append(
                f"Known postal code range: {city_info['ranges'][0][0]}-{city_info['ranges'][0][1]}"
            )
            
        return "\n".join(components)

class Command(BaseCommand):
    help = 'Process and update missing postal codes for non-discarded businesses'
    def add_arguments(self, parser):
        parser.add_argument(
            '--country', 
            type=str,
            help='Filter by country'
        )
        parser.add_argument(
            '--city', 
            type=str,
            help='Filter by city'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=5,  # Smaller default batch size for GPT calls
            help='Number of businesses to process in each GPT call'
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['PENDING', 'REVIEWED', 'IN_PRODUCTION'],
            help='Filter by specific status'
        )

    def get_businesses_without_postal_code(
        self, 
        country: Optional[str] = None, 
        city: Optional[str] = None,
        status: Optional[str] = None
    ):
        """Fetch businesses without postal codes, excluding DISCARDED status"""
        query = Business.objects.filter(
            Q(postal_code__isnull=True) | Q(postal_code='')
        ).filter(
            is_deleted=False
        ).exclude(
            status='DISCARDED'
        )

        if country:
            query = query.filter(country__iexact=country)
        if city:
            query = query.filter(city__iexact=city)
        if status:
            query = query.filter(status=status)
        else:
            query = query.filter(
                status__in=['PENDING', 'REVIEWED', 'IN_PRODUCTION']
            )

        return query.values(
            'id', 
            'title', 
            'address', 
            'street', 
            'city', 
            'country',
            'postal_code', 
            'latitude', 
            'longitude', 
            'status'
        )
    
    @transaction.atomic
    def process_batch(
        self, 
        businesses: List[Dict], 
        processor: PostalCodeProcessor,
        dry_run: bool
    ) -> Dict:
        """Process a batch of businesses"""
        stats = {'processed': 0, 'updated': 0, 'failed': 0}
        
        try:
            # Businesses are already in dict format since we used values()
            business_data = businesses  # No need to convert anymore
            
            # Process batch with GPT
            results = processor.process_batch_with_gpt(business_data)
            
            # Update businesses with results
            for business_id, postal_code in results:
                try:
                    if dry_run:
                        business = next(b for b in businesses if b['id'] == business_id)  # Use dict access
                        self.stdout.write(
                            f"Would update {business['title']} "  # Use dict access
                            f"with postal code: {postal_code}"
                        )
                    else:
                        Business.objects.filter(id=business_id).update(
                            postal_code=postal_code
                        )
                        logger.info(
                            f"Updated postal code for business {business_id}: "
                            f"{postal_code}"
                        )
                    stats['updated'] += 1
                except Exception as e:
                    logger.error(
                        f"Error updating business {business_id}: {str(e)}"
                    )
                    stats['failed'] += 1
                
            stats['processed'] = len(businesses)
            
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}")
            stats['failed'] = len(businesses)
            stats['processed'] = len(businesses)
            
        return stats

    def _build_gpt_prompt(self, business: Dict) -> str:
        """Build prompt for a single business"""
        components = [
            f"ID: {business['id']}",  # Use dict access
            f"Location:",
            f"Address: {business['address']}",  # Use dict access
            f"Street: {business['street']}",    # Use dict access
            f"City: {business['city']}",        # Use dict access
            f"Country: {business['country']}"    # Use dict access
        ]
        
        if business['latitude'] and business['longitude']:  # Use dict access
            components.append(
                f"Coordinates: {business['latitude']}, {business['longitude']}"
            )
            
        return "\n".join(components)

    def handle(self, *args, **options):
        try:
            processor = PostalCodeProcessor()
            country = options['country']
            city = options['city']
            status = options['status']
            dry_run = options['dry_run']
            batch_size = options['batch_size']
            # Get businesses
            businesses = self.get_businesses_without_postal_code(
                country, city, status
            )
            total = businesses.count()
            # Show initial stats
            self.stdout.write(f"\nProcessing {total} non-discarded businesses...")
            if total > 0:
                status_counts = businesses.values('status').annotate(
                    count=Count('id')
                )
                self.stdout.write("Status breakdown:")
                for status_info in status_counts:
                    self.stdout.write(
                        f"  {status_info['status']}: {status_info['count']}"
                    )
            if dry_run:
                self.stdout.write(
                    self.style.WARNING("DRY RUN - No changes will be made")
                )
            # Process in batches
            total_stats = {'processed': 0, 'updated': 0, 'failed': 0}
            
            for i in range(0, total, batch_size):
                batch = list(businesses[i:i + batch_size])
                batch_stats = self.process_batch(batch, processor, dry_run)
                
                # Update total stats
                for key in total_stats:
                    total_stats[key] += batch_stats[key]
                
                # Progress update
                self.stdout.write(
                    f"Processed {total_stats['processed']}/{total} "
                    f"({total_stats['updated']} updated, "
                    f"{total_stats['failed']} failed)"
                )
                
                # Add delay between batches
                if i + batch_size < total:
                    sleep(1)  # Prevent rate limiting
            # Final summary
            self.stdout.write(self.style.SUCCESS("\nProcessing completed:"))
            self.stdout.write(f"Total processed: {total_stats['processed']}")
            self.stdout.write(f"Successfully updated: {total_stats['updated']}")
            self.stdout.write(f"Failed: {total_stats['failed']}")
        except Exception as e:
            logger.error(f"Command error: {str(e)}")
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))

"""
# Process all eligible businesses0
python manage.py process_postal_codes

# Process specific status
python manage.py process_postal_codes --status REVIEWED

# Process with custom batch size
python manage.py process_postal_codes --batch-size 3

# Dry run for specific country and status
python manage.py process_postal_codes --country Greece --status PENDING --dry-run

"""
 

