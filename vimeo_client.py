import os
from vimeo import VimeoClient
from config import settings
from fastapi import HTTPException

# Initialize Vimeo client
client = VimeoClient(
    token=settings.VIMEO_ACCESS_TOKEN,
    key=settings.VIMEO_CLIENT_ID,
    secret=settings.VIMEO_CLIENT_SECRET
)

def upload_to_vimeo(file_path: str, title: str = "Untitled"):
    try:
        # Verify file exists
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")

        # Start the upload
        uri = client.upload(
            file_path,
            data={
                'name': title,  # Set the video title
                'privacy': {'view': 'anybody'}  # Make the video publicly viewable
            }
        )

        # Verify upload success
        if not uri:
            raise Exception("Vimeo upload failed: No URI returned")

        # Get video details
        response = client.get(f"{uri}?fields=link,uri")
        if response.status_code != 200:
            raise Exception(f"Failed to get video details: {response.status_code} - {response.text}")

        video_data = response.json()
        return {
            "vimeo_url": video_data['link'],
            "vimeo_id": video_data['uri'].split('/')[-1]
        }

    except Exception as e:
        # Log the error for debugging
        print(f"Vimeo upload error: {str(e)}")
        raise Exception(f"Vimeo upload failed: {str(e)}") 
    