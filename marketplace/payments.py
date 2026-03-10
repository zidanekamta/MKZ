import secrets
from .models import PaymentTransaction

def initiate_payment(user, amount_fcfa: int, provider: str) -> PaymentTransaction:
    reference = secrets.token_hex(16)
    return PaymentTransaction.objects.create(
        user=user,
        amount_fcfa=amount_fcfa,
        provider=provider,
        status="PENDING",
        reference=reference,
    )

def webhook_simulator(reference: str, success: bool = True) -> PaymentTransaction:
    tx = PaymentTransaction.objects.get(reference=reference)
    tx.status = "SUCCESS" if success else "FAILED"
    tx.save(update_fields=["status"])
    return tx
