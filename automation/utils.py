#from .countries_destinations_translated import city_name_mapping, country_name_mapping
from automation.models import TagMapping
from django.core.exceptions import ObjectDoesNotExist
import logging 

logger = logging.getLogger(__name__)

country_name_mapping = {
    'Italia': 'Italy',
    'España': 'Spain',
    'Alemania': 'Germany',
    'Francia': 'France',
    'Brasil': 'Brazil',
    'Argentina': 'Argentina',
    'México': 'Mexico',
    'Chile': 'Chile',
    'Portugal': 'Portugal',
    'Colombia': 'Colombia',
    'Grecia': 'Greece',
    'India': 'India',
    'Japón': 'Japan',
    'China': 'China',
    'Tailandia': 'Thailand',
    'Australia': 'Australia',
    'Estados Unidos': 'United States',
    'Reino Unido': 'United Kingdom',
    'Canadá': 'Canada',
    'Países Bajos': 'Netherlands',
    'Bélgica': 'Belgium',
    'Suiza': 'Switzerland',
    'Suecia': 'Sweden',
    'Noruega': 'Norway',
    'Dinamarca': 'Denmark',
    'Finlandia': 'Finland',
    'Austria': 'Austria',
    'Irlanda': 'Ireland',
    'Islandia': 'Iceland',
    'Nueva Zelanda': 'New Zealand',
    'Sudáfrica': 'South Africa',
    'Egipto': 'Egypt',
    'Turquía': 'Turkey',
    'Rusia': 'Russia',
    'Corea del Sur': 'South Korea',
    'Vietnam': 'Vietnam',
    'Indonesia': 'Indonesia',
    'Filipinas': 'Philippines',
    'Malasia': 'Malaysia',
    'Singapur': 'Singapore',
    'Túnez': 'Tunisia',
    'Marruecos': 'Morocco'
}

city_name_mapping = {
    'A Coruña': 'A Coruña',
    'Airlie Beach': 'Airlie Beach',
    'Albufeira': 'Albufeira',
    'Amsterdam': 'Amsterdam',
    'Angers': 'Angers',
    'Atenas': 'Athens',
    'Bangkok': 'Bangkok',
    'Barcelona': 'Barcelona',
    'Barranquilla': 'Barranquilla',
    'Berlin': 'Berlin',
    'Bilbao': 'Bilbao',
    'Bogotá': 'Bogotá',
    'Bolonia': 'Bologna',
    'Boston': 'Boston',
    'Braga': 'Braga',
    'Bruselas': 'Brussels',
    'Bucarest': 'Bucharest',
    'Budapest': 'Budapest',
    'Buenos Aires': 'Buenos Aires',
    'Calcuta': 'Kolkata',
    'Cancún': 'Cancun',
    'Cartagena de indias': 'Cartagena',
    'Cerdeña': 'Sardinia',
    'Ciudad de México': 'Mexico City',
    'Ciudad de Panama': 'Panama City',
    'Coimbra': 'Coimbra',
    'Copenhague': 'Copenhagen',
    'Córdoba': 'Córdoba',
    'Dubai': 'Dubai',
    'Dublin': 'Dublin',
    'El Cairo': 'Cairo',
    'El Calafate': 'El Calafate',
    'Estambul': 'Istanbul',
    'Estocolmo': 'Stockholm',
    'Faro': 'Faro',
    'Florencia': 'Florence',
    'Hawaii': 'Hawaii',
    'Ibiza': 'Ibiza',
    'Isla de Mallorca': 'Mallorca',
    'Javea': 'Jávea',
    'Key West': 'Key West',
    'Kioto': 'Kyoto',
    'Lagos': 'Lagos',
    'Las vegas': 'Las Vegas',
    'Lisboa': 'Lisbon',
    'Londres': 'London',
    'Los Angeles': 'Los Angeles',
    'Madrid': 'Madrid',
    'Malaga': 'Malaga',
    'Malta': 'Malta',
    'Marrakesh': 'Marrakesh',
    'Medellín': 'Medellin',
    'Melbourne': 'Melbourne',
    'Miami': 'Miami',
    'Miami Beach': 'Miami Beach',
    'Milan': 'Milan',
    'Montevideo': 'Montevideo',
    'Mykonos': 'Mykonos',
    'New Orleans': 'New Orleans',
    'New York': 'New York',
    'Niza': 'Nice',
    'Nueva Delhi': 'New Delhi',
    'Orlando': 'Orlando',
    'Osaka': 'Osaka',
    'Paris': 'Paris',
    'Pekin': 'Beijing',
    'Perth': 'Perth',
    'Phuket': 'Phuket',
    'Playa del Carmen': 'Playa del Carmen',
    'Porto': 'Porto',
    'Praga': 'Prague',
    'Puerto Limón': 'Puerto Limón',
    'Puerto Rico': 'Puerto Rico',
    'Puerto Vallarta': 'Puerto Vallarta',
    'Punta Cana': 'Punta Cana',
    'Punta del Este': 'Punta del Este',
    'Quarteira': 'Quarteira',
    'Reikiavik': 'Reykjavik',
    'Rio de Janeiro': 'Rio de Janeiro',
    'Roma': 'Rome',
    'Saint Barthelemy': 'Saint Barthelemy',
    'Salvador de Bahia': 'Salvador',
    'Samaná Costa Norte': 'Samana',
    'San Agustin': 'San Agustin',
    'San Carlos de Bariloche': 'Bariloche',
    'San Diego': 'San Diego',
    'San Francisco': 'San Francisco',
    'Santiago de Chile': 'Santiago',
    'Santiago de Compostela': 'Santiago de Compostela',
    'Santo Domingo': 'Santo Domingo',
    'Savannah': 'Savannah',
    'Seul': 'Seoul',
    'Sevilla': 'Seville',
    'Shanghai': 'Shanghai',
    'Sicilia': 'Sicily',
    'Singapur': 'Singapore',
    'Sintra': 'Sintra',
    'Sofia': 'Sofia',
    'Sydney': 'Sydney',
    'São Paulo': 'Sao Paulo',
    'Tel Aviv': 'Tel Aviv',
    'Tijuana': 'Tijuana',
    'Tokio': 'Tokyo',
    'Toledo': 'Toledo',
    'Tunez': 'Tunis',
    'Ushuaia': 'Ushuaia',
    'Valencia': 'Valencia',
    'Vancouver': 'Vancouver',
    'Varsovia': 'Warsaw',
    'Venecia': 'Venice',
    'Viena': 'Vienna',
    'Washington DC': 'Washington DC'
}


def translate_location(city, country):
    """
    Translates city and country names to their English equivalents if mappings exist.
    """
    translated_city = city_name_mapping.get(city, city)  # Default to original name if no mapping found
    translated_country = country_name_mapping.get(country, country)  # Default to original name if no mapping found
    return translated_city, translated_country


def process_scraped_types(scraped_types, main_category=None):
    """
    Process types from scraping before saving to Business model
    Args:
        scraped_types: Can be a list, tuple, or comma-separated string of types
        main_category: Optional main category to ensure it's included
    Returns:
        str: Cleaned, deduplicated, comma-separated string of types
    """
    # Convert input to list of types
    if isinstance(scraped_types, (list, tuple)):
        types_list = [str(t).strip() for t in scraped_types if str(t).strip()]
    elif isinstance(scraped_types, str):
        types_list = [t.strip() for t in scraped_types.split(',') if t.strip()]
    else:
        types_list = []
     
    if main_category: 
        singular_category = main_category.rstrip('s')  
        types_list.append(singular_category)
     
    unique_types = list(dict.fromkeys(types_list))
    return ', '.join(unique_types)

