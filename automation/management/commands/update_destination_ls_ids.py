# management/commands/update_destination_ls_ids.py

from django.core.management.base import BaseCommand
from automation.models import Destination

class Command(BaseCommand):
    help = 'Update destination ls_ids from Excel mapping - Chunk 1'

    def handle(self, *args, **options):
        # Mapping of Spanish names to English names and their corresponding ls_ids (Chunk 1)
        destination_mapping = {
            136: {'english_name': 'A Coruna', 'ls_id': 136},
            23: {'english_name': 'Barcelona', 'ls_id': 23},
            139: {'english_name': 'Benidorm', 'ls_id': 139},
            126: {'english_name': 'Bilbao', 'ls_id': 126},
            112: {'english_name': 'Cordoba', 'ls_id': 112},
            24: {'english_name': 'Ibiza', 'ls_id': 24},
            145: {'english_name': 'Fuerteventura Island', 'ls_id': 145},
            144: {'english_name': 'Lanzarote Island', 'ls_id': 144},
            108: {'english_name': 'Mallorca Island', 'ls_id': 108},
            20: {'english_name': 'Javea', 'ls_id': 20},
            25: {'english_name': 'Madrid', 'ls_id': 25},
            26: {'english_name': 'Malaga', 'ls_id': 26},
            27: {'english_name': 'Santiago de Compostela', 'ls_id': 27},
            28: {'english_name': 'Seville', 'ls_id': 28},
            146: {'english_name': 'Tenerife', 'ls_id': 146},
            110: {'english_name': 'Toledo', 'ls_id': 110},
            2: {'english_name': 'Valencia', 'ls_id': 2},
            141: {'english_name': 'Valladolid', 'ls_id': 141},
            49: {'english_name': 'Albufeira', 'ls_id': 49},
            109: {'english_name': 'Braga', 'ls_id': 109},
            138: {'english_name': 'Coimbra', 'ls_id': 138},
            51: {'english_name': 'Faro', 'ls_id': 51},
            48: {'english_name': 'Lagos', 'ls_id': 48},
            3: {'english_name': 'Lisbon', 'ls_id': 3},
            7: {'english_name': 'Porto', 'ls_id': 7},
            50: {'english_name': 'Quarteira', 'ls_id': 50},
            47: {'english_name': 'Sintra', 'ls_id': 47},
            11: {'english_name': 'Buenos Aires', 'ls_id': 11},
            90: {'english_name': 'El Calafate', 'ls_id': 90},
            12: {'english_name': 'San Carlos de Bariloche', 'ls_id': 12},
            10: {'english_name': 'Ushuaia', 'ls_id': 10},
            14: {'english_name': 'Marrakesh', 'ls_id': 14},
            15: {'english_name': 'Istanbul', 'ls_id': 15},
            16: {'english_name': 'Tunis', 'ls_id': 16},
            17: {'english_name': 'Cairo', 'ls_id': 17},
            18: {'english_name': 'Tel Aviv', 'ls_id': 18},
            19: {'english_name': 'Athens', 'ls_id': 19},
            22: {'english_name': 'Mykonos', 'ls_id': 22},
            29: {'english_name': 'Berlin', 'ls_id': 29},
            30: {'english_name': 'Brussels', 'ls_id': 30},
            31: {'english_name': 'Bucharest', 'ls_id': 31},
            32: {'english_name': 'Budapest', 'ls_id': 32},
            33: {'english_name': 'Copenhagen', 'ls_id': 33},
            34: {'english_name': 'Dublin', 'ls_id': 34},
            35: {'english_name': 'Stockholm', 'ls_id': 35},
            114: {'english_name': 'Bologna', 'ls_id': 114},
            113: {'english_name': 'Sardinia', 'ls_id': 113},
            36: {'english_name': 'Florence', 'ls_id': 36},
            37: {'english_name': 'Milan', 'ls_id': 37},
            38: {'english_name': 'Rome', 'ls_id': 38},
            94: {'english_name': 'Sardegna', 'ls_id': 94},
            39: {'english_name': 'Sicily', 'ls_id': 39},
            40: {'english_name': 'Venice', 'ls_id': 40},
            124: {'english_name': 'Angers', 'ls_id': 124},
            43: {'english_name': 'Nice', 'ls_id': 43},
            42: {'english_name': 'Paris', 'ls_id': 42},
            41: {'english_name': 'Saint Barthelemy', 'ls_id': 41},
            44: {'english_name': 'Prague', 'ls_id': 44},
            52: {'english_name': 'Warsaw', 'ls_id': 52},
            45: {'english_name': 'London', 'ls_id': 45},
            46: {'english_name': 'Malta', 'ls_id': 46},
            53: {'english_name': 'Vienna', 'ls_id': 53},
            54: {'english_name': 'Sofia', 'ls_id': 54},
            69: {'english_name': 'Boston', 'ls_id': 69},
            62: {'english_name': 'Hawaii', 'ls_id': 62},
            140: {'english_name': 'U.S. Virgin Islands', 'ls_id': 140},
            55: {'english_name': 'Key West', 'ls_id': 55},
            57: {'english_name': 'Las Vegas', 'ls_id': 57},
            56: {'english_name': 'Los Angeles', 'ls_id': 56},
            58: {'english_name': 'Miami', 'ls_id': 58},
            59: {'english_name': 'Miami Beach', 'ls_id': 59},
            61: {'english_name': 'New Orleans', 'ls_id': 61},
            60: {'english_name': 'New York', 'ls_id': 60},
            63: {'english_name': 'Orlando', 'ls_id': 63},
            70: {'english_name': 'Puerto Rico', 'ls_id': 70},
            65: {'english_name': 'San Diego', 'ls_id': 65},
            66: {'english_name': 'San Francisco', 'ls_id': 66},
            67: {'english_name': 'Savannah', 'ls_id': 67},
            64: {'english_name': 'St. Augustine', 'ls_id': 64},
            68: {'english_name': 'Washington DC', 'ls_id': 68},
            71: {'english_name': 'Montevideo', 'ls_id': 71},
            72: {'english_name': 'Punta del Este', 'ls_id': 72},
            73: {'english_name': 'Punta Cana', 'ls_id': 73},
            133: {'english_name': 'Samana North Coast', 'ls_id': 133},
            74: {'english_name': 'Santo Domingo', 'ls_id': 74},
            75: {'english_name': 'Panama City', 'ls_id': 75},
            76: {'english_name': 'Puerto Limon', 'ls_id': 76},
            78: {'english_name': 'Barranquilla', 'ls_id': 78},
            79: {'english_name': 'Bogota', 'ls_id': 79},
            80: {'english_name': 'Cartagena de Indias', 'ls_id': 80},
            77: {'english_name': 'Medellin', 'ls_id': 77},
            81: {'english_name': 'Rio de Janeiro', 'ls_id': 81},
            107: {'english_name': 'Salvador de Bahia', 'ls_id': 107},
            82: {'english_name': 'Sao Paulo', 'ls_id': 82},
            83: {'english_name': 'Santiago de Chile', 'ls_id': 83},
            88: {'english_name': 'Cancun', 'ls_id': 88},
            85: {'english_name': 'Mexico City', 'ls_id': 85},
            86: {'english_name': 'Playa del Carmen', 'ls_id': 86},
            87: {'english_name': 'Puerto Vallarta', 'ls_id': 87},
            84: {'english_name': 'Tijuana', 'ls_id': 84},
            21: {'english_name': 'Amsterdam', 'ls_id': 21},
            106: {'english_name': 'Vancouver', 'ls_id': 106},
            111: {'english_name': 'Seoul', 'ls_id': 111},
            135: {'english_name': 'Kyoto', 'ls_id': 135},
            122: {'english_name': 'Osaka', 'ls_id': 122},
            115: {'english_name': 'Tokyo', 'ls_id': 115},
            128: {'english_name': 'Kolkata', 'ls_id': 128},
            118: {'english_name': 'New Delhi', 'ls_id': 118},
            120: {'english_name': 'Beijing', 'ls_id': 120},
            119: {'english_name': 'Shanghai', 'ls_id': 119},
            121: {'english_name': 'Singapore', 'ls_id': 121},
            127: {'english_name': 'Bangkok', 'ls_id': 127},
            123: {'english_name': 'Phuket', 'ls_id': 123},
            125: {'english_name': 'Dubai', 'ls_id': 125},
            129: {'english_name': 'Airlie Beach', 'ls_id': 129},
            132: {'english_name': 'Melbourne', 'ls_id': 132},
            134: {'english_name': 'Perth', 'ls_id': 134},
            130: {'english_name': 'Sydney', 'ls_id': 130},
            137: {'english_name': 'Reykjavik', 'ls_id': 137},            
        }

        updated_count = 0
        created_count = 0
        errors = []

        # Process each destination
        for id, data in destination_mapping.items():
            english_name = data['english_name']
            ls_id = data['ls_id']

            try:
                # First try to find the destination
                destination = Destination.objects.filter(name=english_name).first()
                
                if destination:
                    # If it exists, ONLY update ls_id
                    old_ls_id = destination.ls_id
                    destination.ls_id = ls_id
                    destination.save(update_fields=['ls_id'])  # Only update ls_id field
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Updated destination: {english_name} ls_id from {old_ls_id} to {ls_id}"
                    ))
                else:
                    # If it doesn't exist, create new with minimum required fields
                    destination = Destination.objects.create(
                        name=english_name,
                        ls_id=ls_id,
                        province="Missing province",  # Required field
                        description="Created via management command",  # Required field
                    )
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Created new destination: {english_name} with ls_id: {ls_id}"
                    ))

            except Exception as e:
                errors.append(f"Error processing {english_name}: {str(e)}")
                self.stdout.write(self.style.ERROR(
                    f"Error processing {english_name} (ID: {id}): {str(e)}"
                ))

        # Final summary
        self.stdout.write("\nSummary:")
        self.stdout.write(self.style.SUCCESS(f"Updated destinations: {updated_count}"))
        self.stdout.write(self.style.SUCCESS(f"Created destinations: {created_count}"))

        if errors:
            self.stdout.write("\nErrors:")
            for error in errors:
                self.stdout.write(self.style.ERROR(error))
