from automation.models import Image
from django.core.files.storage import default_storage

def remove_duplicate_images():
    images = Image.objects.all()
    image_paths = {}

    for image in images:
        # Check if the same business has the same image URL or file path multiple times
        if image.image_url in image_paths or image.local_path in image_paths:
            print(f"Deleting duplicate image {image.local_path}")
            
            # Delete the image from storage
            if default_storage.exists(image.local_path):
                default_storage.delete(image.local_path)
            
            # Delete the duplicate image record
            image.delete()
        else:
            image_paths[image.image_url] = True
            image_paths[image.local_path] = True

    print("Duplicate images cleanup completed.")
