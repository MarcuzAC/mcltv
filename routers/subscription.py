# routers/subscription.py
from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from database import get_db
from models import User, SubscriptionPlan
from auth import get_current_user
from paychangu import PayChanguClient
from config import settings

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Initialize PayChangu client
paychangu_client = PayChanguClient(secret_key=settings.PAYCHANGU_SECRET_KEY)

# ─────────────────────────────
# Request/Response Models
# ─────────────────────────────
class SubscriptionPlanCreate(BaseModel):
    name: str
    description: str
    price: float
    currency: str = "MWK"
    duration_days: int
    is_active: bool = True

class SubscriptionPlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    price: float
    currency: str
    duration_days: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class PaymentInitiationRequest(BaseModel):
    plan_id: uuid.UUID
    phone_number: str
    network: str  # "airtel", "tnm", etc.
    email: Optional[str] = None
    callback_url: Optional[str] = None
    return_url: Optional[str] = None

class PaymentVerificationResponse(BaseModel):
    status: str
    amount: float
    currency: str
    transaction_reference: str
    payment_date: datetime
    plan_id: uuid.UUID
    expiry_date: datetime

class UserSubscriptionStatus(BaseModel):
    is_subscribed: bool
    subscription_expiry: Optional[datetime]
    is_active: bool
    current_plan: Optional[SubscriptionPlanResponse]

# ─────────────────────────────
# Subscription Plan Endpoints
# ─────────────────────────────
@router.post("/plans", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new subscription plan (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can create subscription plans"
        )

    db_plan = SubscriptionPlan(**plan_data.dict())
    db.add(db_plan)
    await db.commit()
    await db.refresh(db_plan)
    return db_plan

@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def get_subscription_plans(
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(True)
):
    """Get available subscription plans"""
    query = select(SubscriptionPlan)
    if active_only:
        query = query.where(SubscriptionPlan.is_active == True)
    
    result = await db.execute(query.order_by(SubscriptionPlan.price))
    return result.scalars().all()

@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get details of a specific subscription plan"""
    plan = await db.get(SubscriptionPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    return plan

# ─────────────────────────────
# Payment Processing Endpoints
# ─────────────────────────────
@router.post("/initiate-payment")
async def initiate_subscription_payment(
    payment_request: PaymentInitiationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initiate a subscription payment via PayChangu"""
    # Get the subscription plan
    plan = await db.get(SubscriptionPlan, payment_request.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")
    
    # Create unique transaction reference
    tx_ref = f"sub-{current_user.id}-{uuid.uuid4()}"

    # Initiate payment with PayChangu
    try:
        response = paychangu_client.direct_charge_service.initialize_payment(
            amount=plan.price,
            currency=plan.currency,
            mobile_number=payment_request.phone_number,
            network=payment_request.network,
            reference=tx_ref
        )
        
        return {
            "payment_url": response.get("payment_url"),
            "transaction_reference": tx_ref,
            "verification_url": f"/subscriptions/verify-payment/{tx_ref}",
            "plan_id": str(plan.id)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment initiation failed: {str(e)}"
        )

@router.get("/verify-payment/{transaction_reference}", response_model=PaymentVerificationResponse)
async def verify_payment(
    transaction_reference: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify a payment transaction and activate subscription"""
    try:
        # Verify with PayChangu
        verification = paychangu_client.direct_charge_service.verify_charge(transaction_reference)
        
        if verification.get("status") == "successful":
            # Extract plan ID from transaction reference
            parts = transaction_reference.split('-')
            if len(parts) < 3:
                raise HTTPException(status_code=400, detail="Invalid transaction reference")
            
            plan_id = uuid.UUID(parts[2])
            plan = await db.get(SubscriptionPlan, plan_id)
            
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            # Update user subscription
            current_user.is_subscribed = True
            current_user.subscription_expiry = datetime.utcnow() + timedelta(days=plan.duration_days)
            await db.commit()
            
            return {
                "status": "success",
                "amount": verification.get("amount"),
                "currency": verification.get("currency"),
                "transaction_reference": transaction_reference,
                "payment_date": datetime.utcnow(),
                "plan_id": plan.id,
                "expiry_date": current_user.subscription_expiry
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment not completed or failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment verification failed: {str(e)}"
        )

# ─────────────────────────────
# Webhook Handler
# ─────────────────────────────
@router.post("/webhook")
async def paychangu_webhook(
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Handle PayChangu payment webhooks"""
    try:
        tx_ref = payload.get("tx_ref")
        status = payload.get("status")
        
        if status == "successful":
            # Get transaction details
            transaction = paychangu_client.direct_charge_service.get_charge_details(tx_ref)
            
            # Extract user ID and plan ID from transaction reference
            parts = tx_ref.split('-')
            if len(parts) < 3:
                raise HTTPException(status_code=400, detail="Invalid transaction reference")
            
            user_id = uuid.UUID(parts[1])
            plan_id = uuid.UUID(parts[2])
            
            user = await db.get(User, user_id)
            plan = await db.get(SubscriptionPlan, plan_id)
            
            if user and plan:
                user.is_subscribed = True
                user.subscription_expiry = datetime.utcnow() + timedelta(days=plan.duration_days)
                await db.commit()
                
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook processing failed: {str(e)}"
        )

# ─────────────────────────────
# User Subscription Status
# ─────────────────────────────
@router.get("/status", response_model=UserSubscriptionStatus)
async def get_subscription_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's subscription status with plan details"""
    is_active = current_user.is_subscribed and (
        current_user.subscription_expiry is None or 
        current_user.subscription_expiry > datetime.utcnow()
    )
    
    # Find the user's current plan (simplified - you might need a more robust way)
    current_plan = None
    if current_user.subscription_expiry:
        result = await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.duration_days == (
                (current_user.subscription_expiry - datetime.utcnow()).days
            ))
        )
        current_plan = result.scalars().first()

    return {
        "is_subscribed": current_user.is_subscribed,
        "subscription_expiry": current_user.subscription_expiry,
        "is_active": is_active,
        "current_plan": current_plan
    }