import boto3
import os
from botocore.exceptions import NoCredentialsError, ClientError

def test_do_spaces_credentials():
    """
    Tests the DigitalOcean Spaces credentials by attempting to list objects in a bucket.
    """
    try:
        # Get credentials and configuration from environment variables
        aws_access_key_id = "DO00WFE3FD3TVWRYCKGL" # "DO00E6VE8N2FAMUTRGPG"
        aws_secret_access_key = "3aPRXOH1OL74F5WjAnSrUzWs+XYulE66KZreLNdW5i4"  # "634mXJypzlK+JlCsS8N7R2JccVZRwrRnj6J6+dYI4bE"
        aws_storage_bucket_name = "localsecrets-production"
        # --- THIS IS THE CORRECTED LINE ---
        aws_s3_endpoint_url = "https://fra1.digitaloceanspaces.com" 
        aws_s3_region_name = "fra1"



        # Check if all required environment variables are set
        if not all([aws_access_key_id, aws_secret_access_key, aws_storage_bucket_name, aws_s3_endpoint_url, aws_s3_region_name]):
            print("Error: Make sure you have set the following environment variables:")
            print("AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL, AWS_S3_REGION_NAME")
            return

        print("Attempting to connect to DigitalOcean Spaces...")

        # Create a session and a client
        session = boto3.session.Session()
        client = session.client('s3',
                                region_name=aws_s3_region_name,
                                endpoint_url=aws_s3_endpoint_url,
                                aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key)

        # Attempt to list the objects in the bucket
        response = client.list_objects_v2(Bucket=aws_storage_bucket_name)

        print("\n✅ Connection Successful!")
        print(f"Successfully connected to bucket: {aws_storage_bucket_name}")

        # Optionally, list some objects
        if 'Contents' in response:
            print("\nFirst 5 objects in the bucket:")
            for obj in response['Contents'][:5]:
                print(f"- {obj['Key']}")
        else:
            print("\nThe bucket is empty.")

    except NoCredentialsError:
        print("\n❌ Credentials not available.")
        print("Please provide your credentials via environment variables.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidAccessKeyId':
            print("\n❌ Invalid Access Key ID.")
            print("The AWS Access Key ID you provided does not exist in our records.")
            print("Please double-check your credentials.")
        elif e.response['Error']['Code'] == 'SignatureDoesNotMatch':
            print("\n❌ Signature Does Not Match.")
            print("The request signature we calculated does not match the signature you provided.")
            print("This is often caused by an incorrect AWS Secret Access Key.")
        elif e.response['Error']['Code'] == 'NoSuchBucket':
            print(f"\n❌ Bucket Not Found: {aws_storage_bucket_name}")
            print("The specified bucket does not exist.")
        else:
            print(f"\n❌ An unexpected error occurred: {e}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_do_spaces_credentials()