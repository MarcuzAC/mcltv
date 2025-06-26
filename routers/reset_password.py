import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
import crud
import schemas
import utils
from security import get_password_hash

router = APIRouter()

@router.post("/forgot-password")
async def forgot_password(request: schemas.ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    # Check if the user exists
    user = await crud.get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate a reset token
    reset_token = utils.create_reset_token(request.email)

    # Save the token in the database
    user.reset_token = reset_token
    await db.commit()

    # Send the token via email
    await utils.send_reset_email(request.email, reset_token)

    return {"message": "Password reset token sent to your email"}

@router.post("/reset-password")
async def reset_password(request: schemas.ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    # Verify the token
    try:
        payload = jwt.decode(request.token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Check if the user exists
    user = await crud.get_user_by_email(db, email)
    if not user or user.reset_token != request.token:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Update the password
    user.hashed_password = get_password_hash(request.new_password)
    user.reset_token = None  # Clear the reset token
    await db.commit()

    return {"message": "Password reset successfully"}