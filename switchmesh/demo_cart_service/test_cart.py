from switchmesh.demo_cart_service.app import CartItem, calculate_checkout_total


def test_normal_order_total():
    result = calculate_checkout_total([CartItem(name="mug", price=20, quantity=2)])

    assert result["subtotal"] == 40.0
    assert result["discount"] == 0.0
    assert result["shipping"] == 5.0
    assert result["total"] == 45.0


def test_save10_discount():
    result = calculate_checkout_total([CartItem(name="shirt", price=50)], "SAVE10")

    assert result["subtotal"] == 50.0
    assert result["discount"] == 5.0
    assert result["shipping"] == 0.0
    assert result["total"] == 45.0


def test_freeship_promo():
    result = calculate_checkout_total([CartItem(name="book", price=20)], "FREESHIP")

    assert result["subtotal"] == 20.0
    assert result["discount"] == 0.0
    assert result["shipping"] == 0.0
    assert result["total"] == 20.0
