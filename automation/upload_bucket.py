#automation/upload_bucket.py
import os
import boto3
import click
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de DigitalOcean Spaces
spaces_endpoint_url = f"https://{os.getenv('AWS_S3_REGION_NAME')}.digitaloceanspaces.com"
spaces_access_key = os.getenv('AWS_ACCESS_KEY_ID')
spaces_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
spaces_bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')

# Crear una sesión de boto3
session = boto3.session.Session()

# Crear un cliente de S3 para DigitalOcean Spaces
s3_client = session.client('s3',
                           region_name=os.getenv('AWS_S3_REGION_NAME'),
                           endpoint_url=spaces_endpoint_url,
                           aws_access_key_id=spaces_access_key,
                           aws_secret_access_key=spaces_secret_key)
@click.command()
@click.option('--bucket',
    default=spaces_bucket_name,
    help='The name of the S3 bucket to upload to')
@click.option('--prefix',
    default='media/',
    help='The prefix (folder) to upload to inside the bucket')
@click.option('--local-dir',
    default='media/',
    help='The local directory to upload from')

def upload_folder_to_s3(bucket: str, prefix: str, local_dir: str):
    """
    Sube una carpeta local a DigitalOcean Spaces y establece permisos de lectura pública.

    :param bucket: Nombre del bucket para subir los archivos
    :param prefix: Prefijo (carpeta) dentro del bucket
    :param local_dir: Directorio local para subir
    """
    if not os.path.exists(local_dir):
        raise click.ClickException(f"The local directory {local_dir} does not exist")

    # Crear un conjunto para almacenar los directorios únicos
    unique_dirs = set()

    for root, dirs, files in os.walk(local_dir):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_dir)
            s3_path = os.path.join(prefix, relative_path).replace("\\", "/")

            # Agregar el directorio padre a unique_dirs
            parent_dir = os.path.dirname(s3_path)
            if parent_dir:
                unique_dirs.add(parent_dir)

            try:
                click.echo(f"Uploading {local_path} to {s3_path}")
                
                # Subir el archivo con ACL público-lectura
                s3_client.upload_file(
                    local_path, 
                    bucket, 
                    s3_path,
                    ExtraArgs={'ACL': 'public-read'}
                )
                
                # Establecer el tipo de contenido adecuado para imágenes
                if s3_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    content_type = f"image/{os.path.splitext(s3_path)[1][1:].lower()}"
                    s3_client.put_object_acl(Bucket=bucket, Key=s3_path, ACL='public-read')
                    s3_client.copy_object(
                        Bucket=bucket,
                        CopySource={'Bucket': bucket, 'Key': s3_path},
                        Key=s3_path,
                        MetadataDirective='REPLACE',
                        ContentType=content_type,
                        ACL='public-read'
                    )

            except ClientError as e:
                click.echo(f"Error uploading {local_path}: {e}", err=True)

    # Establecer permisos de lectura pública para los directorios
    for dir_path in unique_dirs:
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=f"{dir_path}/",
                ACL='public-read'
            )
            click.echo(f"Set public-read permissions for directory: {dir_path}/")
        except ClientError as e:
            click.echo(f"Error setting permissions for directory {dir_path}: {e}", err=True)

    click.echo("Upload completed")

@click.command()
@click.option('--bucket',
    default=spaces_bucket_name,
    help='The name of the S3 bucket to list')
@click.option('--prefix',
    default='',
    help='The prefix (folder) to list inside the bucket')
def list_files(bucket: str, prefix: str):
    """
    Lista los archivos en un bucket de DigitalOcean Spaces.

    :param bucket: Nombre del bucket
    :param prefix: Prefijo (carpeta) para listar
    """
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' in response:
            for obj in response['Contents']:
                click.echo(f"- {obj['Key']}")
        else:
            click.echo("The bucket is empty or the prefix doesn't exist.")
    except ClientError as e:
        click.echo(f"Error listing files: {e}", err=True)

@click.command()
@click.option('--bucket',
    default=spaces_bucket_name,
    help='The name of the S3 bucket to delete from')
@click.option('--key',
    required=True,
    help='The key (path) of the file to delete in the bucket')
def delete_file(bucket: str, key: str):
    """
    Elimina un archivo de DigitalOcean Spaces.

    :param bucket: Nombre del bucket
    :param key: Clave (ruta) del archivo a eliminar
    """
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        click.echo(f"File {key} deleted successfully from bucket {bucket}")
    except ClientError as e:
        click.echo(f"Error deleting file {key}: {e}", err=True)

@click.group()
def cli():
    """Herramienta de línea de comandos para gestionar archivos en DigitalOcean Spaces."""
    pass

cli.add_command(upload_folder_to_s3)
cli.add_command(list_files)
cli.add_command(delete_file)

if __name__ == '__main__':
    cli()

#python upload_bucket.py list-files --bucket business-images --prefix uploads/
#python upload_bucket.py upload-folder-to-s3 --bucket business-images --prefix media/ --local-dir ./media
