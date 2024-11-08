from django.db import transaction
from automation.models import Level, Category, Subcategory

def slugify(text, id=None):
    slug = text.lower().replace(' ', '_').replace('(', '').replace(')', '')
    if id is not None:
        slug = f"{slug}_{id}"
    return slug

data = [
    [50, 'Arroces', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [141, 'Bares con puesta del Sol', 141, 'Bares', 1, 'Comer y Beber'],
    [108, 'Beach club', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [173, 'Bio', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [56, 'Carnes - Parrilla', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [36, 'Comida Asiática', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [164, 'Comida China', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [162, 'Comida Coreana', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [180, 'Comida Española', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [168, 'Comida India', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [34, 'Comida Italiana', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [163, 'Comida Japonesa', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [171, 'Comida Mexicana', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [169, 'Comida Nepalí', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [170, 'Comida Peruana', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [166, 'Comida Tailandesa', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [167, 'Comida Taiwanesa', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [165, 'Comida Vietnamita', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [35, 'Especialidad Local', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [39, 'Guía Michelin', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [181, 'Hamburguesería', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [33, 'Mariscos y Pescado', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [130, 'Restaurante Gourmet', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [178, 'Restaurante Venezolano', 196, 'Restaurantes (Cocina Internacional)', 1, 'Comer y Beber'],
    [129, 'Tapas', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [37, 'Vegano', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [172, 'Vegetariano', 17, 'Restaurantes', 1, 'Comer y Beber'],
    [179, 'Bar con Música', 205, 'Local Nocturno', 3, 'Vida Nocturna'],
    [146, 'Bingo', 188, 'Ocio Nocturno', 3, 'Vida Nocturna'],
    [145, 'Casino', 188, 'Ocio Nocturno', 3, 'Vida Nocturna'],
    [82, 'Bodyboard', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [153, 'Buceo', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [125, 'Campo de Béisbol', 117, 'Deportes de Campo', 6, '¿Qué hacer?'],
    [95, 'Campo de Golf', 117, 'Deportes de Campo', 6, '¿Qué hacer?'],
    [93, 'Campo de Tenis', 117, 'Deportes de Campo', 6, '¿Qué hacer?'],
    [128, 'Centros de entretenimiento Infantil', 192, 'En Familia', 6, '¿Qué hacer?'],
    [96, 'Circuitos de Velocidad', 117, 'Deportes de Campo', 6, '¿Qué hacer?'],
    [182, 'Deportes de Aventura', 88, 'Naturaleza y Aventura', 6, '¿Qué hacer?'],
    [113, 'Estación de Esquí', 117, 'Deportes de Campo', 6, '¿Qué hacer?'],
    [152, 'Guia turístico', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [81, 'Kitesurf', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [98, 'Parques Naturales', 88, 'Naturaleza y Aventura', 6, '¿Qué hacer?'],
    [151, 'Paseo Urbano', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [136, 'Paseos en Barco', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [114, 'Piscina deportiva', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [131, 'Pista de Padel', 117, 'Deportes de Campo', 6, '¿Qué hacer?'],
    [100, 'Rutas de Peregrinaje', 88, 'Naturaleza y Aventura', 6, '¿Qué hacer?'],
    [99, 'Rutas de Senderismo', 88, 'Naturaleza y Aventura', 6, '¿Qué hacer?'],
    [80, 'Surf', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [138, 'Tour Aventura', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [137, 'Tour Aéreo', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [139, 'Tour Calesa de caballos', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [135, 'Tour de Bicicletas', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [149, 'Tours en Bicitaxi', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [133, 'Tuc Tuc', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [84, 'Vela', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [150, 'Viaje de un día', 173, 'Tour Guiado', 6, '¿Qué hacer?'],
    [83, 'Wakeboard', 124, 'Deportes Acuaticos', 6, '¿Qué hacer?'],
    [119, 'Hotel Boutique', 82, 'Hoteles', 12, 'Alojamiento'],
    [122, 'Hotel Low Cost', 82, 'Hoteles', 12, 'Alojamiento'],
    [124, 'Hotel Temáticos', 82, 'Hoteles', 12, 'Alojamiento'],
    [123, 'Hotel de aeropuerto', 82, 'Hoteles', 12, 'Alojamiento'],
    [121, 'Hotel de lujo', 82, 'Hoteles', 12, 'Alojamiento'],
    [120, 'Hotel resort', 82, 'Hoteles', 12, 'Alojamiento'],
    [177, 'Comida en Conserva', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [118, 'Gourmet', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [143, 'Herbolario', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [159, 'Lenceria Femenina', 193, 'Ropa', 13, 'Compras'],
    [107, 'Licores y vinos', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [156, 'Moda Hombre', 193, 'Ropa', 13, 'Compras'],
    [157, 'Moda Mujer', 193, 'Ropa', 13, 'Compras'],
    [158, 'Moda Tradicional Local', 193, 'Ropa', 13, 'Compras'],
    [109, 'Sex Shops', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [127, 'Tiendas de Queso', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [117, 'Tiendas de Té', 143, 'Tiendas Especializadas', 13, 'Compras'],
    [176, 'Zapatería', 193, 'Ropa', 13, 'Compras'],
    [58, 'Escultura', 104, 'Monumentos', 16, '¿Qué ver?'],
    [57, 'Estátua', 104, 'Monumentos', 16, '¿Qué ver?'],
    [62, 'Lugares de Culto', 22, 'Patrimonio histórico', 16, '¿Qué ver?'],
    [59, 'Monolito', 104, 'Monumentos', 16, '¿Qué ver?'],
    [64, 'Bus Turístico', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [69, 'Tour Fotográfico', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [66, 'Tours Aéreos', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [70, 'Tours en Barco', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [68, 'Tours en Bici-Taxi', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [67, 'Tours en Coche de Caballos', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [65, 'Tours en Segway', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [71, 'Tours en Tuc-Tuc', 45, 'Tour Guiado', 23, '¿Qué hacer?'],
    [88, 'Baloncesto', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [91, 'Baseball', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [85, 'Fórmula 1', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [87, 'Fútbol', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [86, 'Motociclismo', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [90, 'Paddel', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [92, 'Rugby', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [89, 'Tenis', 159, 'Eventos Deportivos', 24, 'Deporte'],
    [101, 'Aeropuerto', 189, 'Transporte Público', 29, 'Transporte'],
    [154, 'Chofer privado con vehículo', 190, 'Transporte Privado', 29, 'Transporte'],
    [103, 'Estación de Autobuses', 189, 'Transporte Público', 29, 'Transporte'],
    [126, 'Estación de Metro', 189, 'Transporte Público', 29, 'Transporte'],
    [102, 'Estación de Tren', 189, 'Transporte Público', 29, 'Transporte'],
    [116, 'Operador de Metro', 189, 'Transporte Público', 29, 'Transporte'],
    [147, 'Taxi', 190, 'Transporte Privado', 29, 'Transporte'],
    [148, 'Transporte al aeropuerto', 190, 'Transporte Privado', 29, 'Transporte']
]


# Diccionarios para almacenar objetos creados
levels = {}
categories = {}

@transaction.atomic
def insert_data():
    # Diccionarios para almacenar objetos creados
    levels = {}
    categories = {}

    # Insertar Niveles
    for item in data:
        level_id, level_title = item[4], item[5]
        if level_id not in levels:
            level, created = Level.objects.update_or_create(id=level_id, defaults={'title': level_title})
            levels[level_id] = level
            print(f"{'Created' if created else 'Retrieved'} Level: {level_title}")

    # Insertar Categorías
    for item in data:
        category_id, category_title, level_id = item[2], item[3], item[4]
        if category_id not in categories:
            category, created = Category.objects.update_or_create(
                id=category_id,
                defaults={
                    'title': category_title,
                    'value': slugify(category_title, category_id),
                    'level': levels[level_id]
                }
            )
            categories[category_id] = category
            print(f"{'Created' if created else 'Updated'} Category: {category_title}")

    # Insertar Subcategorías
    for item in data:
        subcategory_id, subcategory_title, category_id = item[0], item[1], item[2]
        if category_id in categories:  # Asegurarse de que la categoría existe
            subcategory, created = Subcategory.objects.update_or_create(
                id=subcategory_id,
                defaults={
                    'title': subcategory_title,
                    'category': categories[category_id]
                }
            )
            print(f"{'Created' if created else 'Retrieved'} Subcategory: {subcategory_title}")
        else:
            print(f"Warning: Category {category_id} not found for Subcategory {subcategory_title}")

    print(f"Niveles: {Level.objects.count()}")
    print(f"Categorías: {Category.objects.count()}")
    print(f"Subcategorías: {Subcategory.objects.count()}")

if __name__ == "__main__":
    insert_data()


 
