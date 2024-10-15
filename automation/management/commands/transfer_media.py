from django.core.management.base import BaseCommand
import os
import boto3
from django.conf import settings
from botocore.exceptions import ClientError

class Command(BaseCommand):
    help = 'Transfer media files from server to DigitalOcean Spaces'

    def handle(self, *args, **options):
        session = boto3.session.Session()
        client = session.client('s3',
                                region_name=settings.AWS_S3_REGION_NAME,
                                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

        media_root = settings.MEDIA_ROOT
        for root, dirs, files in os.walk(media_root):
            for filename in files:
                local_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_path, media_root)
                s3_key = os.path.join('media', relative_path).replace("\\", "/")

                try:
                    client.upload_file(local_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
                    self.stdout.write(self.style.SUCCESS(f"Uploaded {local_path} to {s3_key}"))
                except ClientError as e:
                    self.stdout.write(self.style.ERROR(f"Error uploading {local_path}: {e}"))

        self.stdout.write(self.style.SUCCESS('Media transfer completed'))

#python manage.py transfer_media
