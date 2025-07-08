import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

class Settings:
    # Vimeo Configuration
    VIMEO_CLIENT_ID = os.getenv("VIMEO_CLIENT_ID")
    VIMEO_CLIENT_SECRET = os.getenv("VIMEO_CLIENT_SECRET")
    VIMEO_ACCESS_TOKEN = os.getenv("VIMEO_ACCESS_TOKEN")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_PUBLIC_KEY = os.getenv("SUPABASE_PUBLIC_KEY")
    SUPABASE_PRIVATE_KEY = os.getenv("SUPABASE_PRIVATE_KEY")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "news-images")

    PAYCHANGU_SECRET_KEY = os.getenv("PAYCHANGU_SECRET_KEY")

    APK_DOWNLOAD_URL = os.getenv("APK_DOWNLOAD_URL")

    def __init__(self):
        self._supabase = create_client(self.SUPABASE_URL, self.SUPABASE_PRIVATE_KEY)

    @property
    def supabase(self) -> Client:
        return self._supabase

# Instantiate settings
settings = Settings()

# Explicitly expose supabase for import
supabase = settings.supabase