"""
Payment Service using Stripe
Handles subscriptions, one-time payments, and billing
"""
import os
import stripe
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


class PaymentService:
    """
    Payment service for handling Stripe payments
    """
    
    # Pricing plans
    PLANS = {
        "free": {
            "name": "Free",
            "price": 0,
            "features": [
                "1 project",
                "Up to 2 videos",
                "Basic 3D reconstruction",
                "Community support"
            ],
            "limits": {
                "projects": 1,
                "videos_per_project": 2,
                "storage_gb": 1,
                "processing_hours": 1
            }
        },
        "starter": {
            "name": "Starter",
            "price": 29,
            "stripe_price_id": os.getenv("STRIPE_STARTER_PRICE_ID"),
            "features": [
                "5 projects",
                "Up to 10 videos per project",
                "HD 3D reconstruction",
                "Voice cloning",
                "Email support"
            ],
            "limits": {
                "projects": 5,
                "videos_per_project": 10,
                "storage_gb": 10,
                "processing_hours": 10
            }
        },
        "pro": {
            "name": "Pro",
            "price": 99,
            "stripe_price_id": os.getenv("STRIPE_PRO_PRICE_ID"),
            "features": [
                "Unlimited projects",
                "Unlimited videos",
                "4K 3D reconstruction",
                "Voice cloning",
                "AI conversations",
                "Priority support",
                "API access"
            ],
            "limits": {
                "projects": -1,  # Unlimited
                "videos_per_project": -1,
                "storage_gb": 100,
                "processing_hours": 50
            }
        },
        "enterprise": {
            "name": "Enterprise",
            "price": 299,
            "stripe_price_id": os.getenv("STRIPE_ENTERPRISE_PRICE_ID"),
            "features": [
                "Everything in Pro",
                "Dedicated GPU",
                "Custom integrations",
                "White-label option",
                "24/7 support",
                "SLA guarantee"
            ],
            "limits": {
                "projects": -1,
                "videos_per_project": -1,
                "storage_gb": 500,
                "processing_hours": 200
            }
        }
    }
    
    # One-time services
    SERVICES = {
        "dataset_export": {
            "name": "Dataset Export",
            "price": 49,
            "description": "Export project as robot training dataset (USD/ROS format)"
        },
        "custom_processing": {
            "name": "Custom Processing",
            "price": 99,
            "description": "Custom video processing with dedicated resources"
        },
        "vr_experience": {
            "name": "VR Experience Package",
            "price": 199,
            "description": "Complete VR experience with interactive characters"
        }
    }
    
    def __init__(self):
        """Initialize payment service"""
        if not stripe.api_key:
            logger.warning("Stripe API key not configured")
        
        logger.info("Payment service initialized")
    
    def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create Stripe customer
        
        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata
            
        Returns:
            Customer data
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            logger.info(f"Created Stripe customer: {customer.id}")
            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {e}")
            raise
    
    def create_subscription(
        self,
        customer_id: str,
        plan: str,
        trial_days: int = 0
    ) -> Dict:
        """
        Create subscription
        
        Args:
            customer_id: Stripe customer ID
            plan: Plan name (starter, pro, enterprise)
            trial_days: Trial period in days
            
        Returns:
            Subscription data
        """
        if plan not in self.PLANS or plan == "free":
            raise ValueError(f"Invalid plan: {plan}")
        
        plan_data = self.PLANS[plan]
        price_id = plan_data.get("stripe_price_id")
        
        if not price_id:
            raise ValueError(f"Price ID not configured for plan: {plan}")
        
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days if trial_days > 0 else None,
                metadata={"plan": plan}
            )
            
            logger.info(f"Created subscription: {subscription.id}")
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "trial_end": subscription.trial_end,
                "plan": plan
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating subscription: {e}")
            raise
    
    def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> Dict:
        """
        Cancel subscription
        
        Args:
            subscription_id: Subscription ID
            at_period_end: Cancel at end of billing period
            
        Returns:
            Cancellation data
        """
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)
            
            logger.info(f"Cancelled subscription: {subscription_id}")
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "cancel_at": subscription.cancel_at
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {e}")
            raise
    
    def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create payment intent for one-time payment
        
        Args:
            amount: Amount in cents
            currency: Currency code
            customer_id: Optional customer ID
            metadata: Additional metadata
            
        Returns:
            Payment intent data
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            
            logger.info(f"Created payment intent: {intent.id}")
            return {
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": intent.amount,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {e}")
            raise
    
    def purchase_service(
        self,
        customer_id: str,
        service: str
    ) -> Dict:
        """
        Purchase one-time service
        
        Args:
            customer_id: Customer ID
            service: Service name
            
        Returns:
            Payment intent data
        """
        if service not in self.SERVICES:
            raise ValueError(f"Invalid service: {service}")
        
        service_data = self.SERVICES[service]
        amount = service_data["price"] * 100  # Convert to cents
        
        return self.create_payment_intent(
            amount=amount,
            customer_id=customer_id,
            metadata={
                "service": service,
                "description": service_data["description"]
            }
        )
    
    def get_subscription(self, subscription_id: str) -> Dict:
        """Get subscription details"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "plan": subscription.metadata.get("plan", "unknown")
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving subscription: {e}")
            raise
    
    def get_customer_subscriptions(self, customer_id: str) -> List[Dict]:
        """Get all subscriptions for customer"""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status="all"
            )
            
            return [
                {
                    "subscription_id": sub.id,
                    "status": sub.status,
                    "plan": sub.metadata.get("plan", "unknown"),
                    "current_period_end": sub.current_period_end
                }
                for sub in subscriptions.data
            ]
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error listing subscriptions: {e}")
            raise
    
    def create_checkout_session(
        self,
        customer_id: str,
        plan: str,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Create Stripe Checkout session
        
        Args:
            customer_id: Customer ID
            plan: Plan name
            success_url: Success redirect URL
            cancel_url: Cancel redirect URL
            
        Returns:
            Checkout session data
        """
        if plan not in self.PLANS or plan == "free":
            raise ValueError(f"Invalid plan: {plan}")
        
        plan_data = self.PLANS[plan]
        price_id = plan_data.get("stripe_price_id")
        
        if not price_id:
            raise ValueError(f"Price ID not configured for plan: {plan}")
        
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"plan": plan}
            )
            
            logger.info(f"Created checkout session: {session.id}")
            return {
                "session_id": session.id,
                "url": session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise
    
    def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> Dict:
        """
        Create billing portal session
        
        Args:
            customer_id: Customer ID
            return_url: Return URL
            
        Returns:
            Portal session data
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            
            logger.info(f"Created billing portal session for customer: {customer_id}")
            return {
                "url": session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal session: {e}")
            raise
    
    def handle_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> Dict:
        """
        Handle Stripe webhook
        
        Args:
            payload: Webhook payload
            signature: Stripe signature
            
        Returns:
            Event data
        """
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if not webhook_secret:
            raise ValueError("Webhook secret not configured")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            
            logger.info(f"Received webhook event: {event['type']}")
            
            # Handle different event types
            if event['type'] == 'customer.subscription.created':
                self._handle_subscription_created(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.updated':
                self._handle_subscription_updated(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.deleted':
                self._handle_subscription_deleted(event['data']['object'])
            
            elif event['type'] == 'payment_intent.succeeded':
                self._handle_payment_succeeded(event['data']['object'])
            
            elif event['type'] == 'payment_intent.payment_failed':
                self._handle_payment_failed(event['data']['object'])
            
            return {"status": "success", "event_type": event['type']}
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise
    
    def _handle_subscription_created(self, subscription):
        """Handle subscription created event"""
        logger.info(f"Subscription created: {subscription['id']}")
        # TODO: Update user subscription in database
    
    def _handle_subscription_updated(self, subscription):
        """Handle subscription updated event"""
        logger.info(f"Subscription updated: {subscription['id']}")
        # TODO: Update user subscription in database
    
    def _handle_subscription_deleted(self, subscription):
        """Handle subscription deleted event"""
        logger.info(f"Subscription deleted: {subscription['id']}")
        # TODO: Downgrade user to free plan
    
    def _handle_payment_succeeded(self, payment_intent):
        """Handle payment succeeded event"""
        logger.info(f"Payment succeeded: {payment_intent['id']}")
        # TODO: Fulfill order/service
    
    def _handle_payment_failed(self, payment_intent):
        """Handle payment failed event"""
        logger.error(f"Payment failed: {payment_intent['id']}")
        # TODO: Notify user of payment failure
    
    def get_usage_stats(self, user_id: int) -> Dict:
        """
        Get usage statistics for user
        
        Args:
            user_id: User ID
            
        Returns:
            Usage statistics
        """
        # TODO: Get from database
        return {
            "projects_used": 2,
            "videos_uploaded": 8,
            "storage_used_gb": 5.2,
            "processing_hours_used": 3.5
        }
    
    def check_limits(
        self,
        user_id: int,
        plan: str,
        action: str
    ) -> bool:
        """
        Check if user can perform action based on plan limits
        
        Args:
            user_id: User ID
            plan: User's plan
            action: Action to check (create_project, upload_video, etc.)
            
        Returns:
            True if allowed, False otherwise
        """
        if plan not in self.PLANS:
            return False
        
        limits = self.PLANS[plan]["limits"]
        usage = self.get_usage_stats(user_id)
        
        if action == "create_project":
            max_projects = limits["projects"]
            if max_projects == -1:  # Unlimited
                return True
            return usage["projects_used"] < max_projects
        
        elif action == "upload_video":
            max_videos = limits["videos_per_project"]
            if max_videos == -1:  # Unlimited
                return True
            # TODO: Check per-project limit
            return True
        
        elif action == "use_storage":
            max_storage = limits["storage_gb"]
            return usage["storage_used_gb"] < max_storage
        
        elif action == "process_video":
            max_hours = limits["processing_hours"]
            return usage["processing_hours_used"] < max_hours
        
        return False


# Example usage
if __name__ == "__main__":
    service = PaymentService()
    
    # Create customer
    customer = service.create_customer(
        email="user@example.com",
        name="Test User"
    )
    
    # Create subscription
    subscription = service.create_subscription(
        customer_id=customer["customer_id"],
        plan="pro",
        trial_days=14
    )
    
    print(f"Created subscription: {subscription}")

# Made with Bob
