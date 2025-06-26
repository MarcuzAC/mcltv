# utils.py
from jose import JWTError, jwt
from datetime import datetime, timedelta
import aiosmtplib
from email.message import EmailMessage
import os
import uuid
from fastapi import HTTPException, status
from config import supabase, settings
from typing import Optional
from fastapi import UploadFile
from pathlib import Path

# JWT Configuration
SECRET_KEY = "your-secret-key"  
ALGORITHM = "HS256"
RESET_TOKEN_EXPIRE_MINUTES = 30

# Email Configuration
SMTP_SERVER = "aspmx.l.google.com"  
SMTP_PORT = 25
SMTP_USERNAME = "MarcuzAC"  
SMTP_PASSWORD = "Fizosat2010"  

def create_reset_token(email: str) -> str:
    expires = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "exp": expires}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def send_reset_email(email: str, token: str):
    message = EmailMessage()
    message["From"] = SMTP_USERNAME
    message["To"] = email
    message["Subject"] = "Password Reset Request"
    message.set_content(f"Use this token to reset your password: {token}")

    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        username=SMTP_USERNAME,
        password=SMTP_PASSWORD,
        use_tls=True,
    )

async def upload_to_supabase(file: UploadFile, file_path: str) -> str:
    """Upload file to Supabase storage"""
    try:
        contents = await file.read()
        res = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            file=contents,
            path=file_path,
            file_options={"content-type": file.content_type}
        )
        return supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(file_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )

async def delete_from_supabase(file_path: str) -> bool:
    """Delete file from Supabase storage"""
    try:
        res = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([file_path])
        return True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )

async def upload_news_image(file: UploadFile) -> str:
    """Upload news image with organized path structure"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed"
        )

    file_ext = Path(file.filename).suffix.lower()
    date_path = datetime.now().strftime("%Y/%m/%d")
    file_path = f"news/{date_path}/{uuid.uuid4()}{file_ext}"
    return await upload_to_supabase(file, file_path)

async def delete_news_image(image_url: str) -> bool:
    """Delete news image from Supabase"""
    if not image_url:
        return True
        
    base_path = f"{supabase.storage_url}/object/public/{settings.SUPABASE_STORAGE_BUCKET}/"
    if not image_url.startswith(base_path):
        raise ValueError("Invalid image URL format")
        
    file_path = image_url[len(base_path):].split('?')[0]
    return await delete_from_supabase(file_path)