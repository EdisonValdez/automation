import os
import boto3
from django.conf import settings
from botocore.exceptions import ClientError

def transfer_media_to_spaces():
    # Configurar el cliente de S3 (DigitalOcean Spaces usa la API de S3)
    session = boto3.session.Session()
    client = session.client('s3',
                            region_name=settings.AWS_S3_REGION_NAME,
                            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

    # Recorrer todos los archivos en MEDIA_ROOT
    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
        for filename in files:
            local_path = os.path.join(root, filename)
            
            # Crear la clave (path) para el archivo en el bucket
            relative_path = os.path.relpath(local_path, settings.MEDIA_ROOT)
            s3_key = os.path.join('media', relative_path).replace("\\", "/")

            # Subir el archivo al bucket
            try:
                client.upload_file(local_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
                print(f"Uploaded {local_path} to {s3_key}")
            except ClientError as e:
                print(f"Error uploading {local_path}: {e}")

if __name__ == "__main__":
    transfer_media_to_spaces()
