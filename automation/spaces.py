import boto3
from botocore.client import Config
import os

"""SPACE_NAME = os.getenv('SPACE_NAME')
REGION = os.getenv('REGION')
ACCESS_KEY = os.getenv('ACCESS_KEY')
SECRET_KEY = os.getenv('SECRET_KEY') """

# Configuration variables
SPACE_NAME = 'businesses'  
REGION = 'nyc3'  
ACCESS_KEY = 'DO00E6VE8N2FAMUTRGPG'  
SECRET_KEY = '634mXJypzlK+JlCsS8N7R2JccVZRwrRnj6J6+dYI4bE'  

# Initialize session and client
session = boto3.session.Session()
client = session.client('s3',
        region_name=REGION,
        endpoint_url=f'https://{REGION}.digitaloceanspaces.com',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY)

def upload_image(file_path, object_name=None):
    """Upload an image to DigitalOcean Space and make it public.

    :param file_path: File path to the image to upload.
    :param object_name: S3 object name. If not specified, file_path is used.
    :return: URL of the uploaded image.
    """
    if object_name is None:
        object_name = os.path.basename(file_path)

    try:
        client.upload_file(
            Filename=file_path,
            Bucket=SPACE_NAME,
            Key=object_name,
            ExtraArgs={
                'ACL': 'public-read',   
                'ContentType': 'image/jpeg'  
            }
        )
        print(f"File {file_path} uploaded successfully.")
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

    # Construct the URL of the uploaded image
    url = f"https://{SPACE_NAME}.{REGION}.digitaloceanspaces.com/{object_name}"
    return url

if __name__ == "__main__":
    # Replace with the path to your image
    image_path = 'C:/Users/Usuari/Desktop/projects/scraping/media/business_images/1/hampton_by_hilton_santo_domingo_airport_2.jpg' 
    object_name = None  # Or 'folder/subfolder/image.jpg'

    # Upload the image
    image_url = upload_image(image_path, object_name)

    if image_url:
        print(f"Image is accessible at: {image_url}")
    else:
        print("Failed to upload image.")
