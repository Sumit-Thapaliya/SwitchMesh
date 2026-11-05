from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROMO_CODES = {
    "SAVE10": {"discount_pct": 10},
    "FREESHIP": {"discount_pct": None, "free_shipping": True},
}


class CartItem(BaseModel):
    name: str = "item"
    price: float = Field(gt=0)
    quantity: int = Field(default=1, gt=0)


class CheckoutRequest(BaseModel):
    items: list[CartItem] = Field(min_length=1)
    promo_code: str | None = None


def calculate_checkout_total(items: list[CartItem], promo_code: str | None = None) -> dict[str, float | str | None]:
    subtotal = sum(item.price * item.quantity for item in items)
    discount = 0.0
    shipping = 0.0 if subtotal >= 50 else 5.0

    if promo_code:
        promo = PROMO_CODES.get(promo_code.upper())
        if promo is None:
            raise ValueError(f"Unknown promo code: {promo_code}")

        discount_pct = promo.get("discount_pct")
        if discount_pct is not None:
            discount = subtotal * (discount_pct / 100)
        if promo.get("free_shipping"):
            shipping = 0.0

    total = subtotal - discount + shipping
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "shipping": round(shipping, 2),
        "total": round(total, 2),
        "promo_code": promo_code.upper() if promo_code else None,
    }


app = FastAPI(title="Demo Cart Service")


@app.post("/checkout")
def checkout(request: CheckoutRequest):
    try:
        return calculate_checkout_total(request.items, request.promo_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
