from marshmallow import Schema, fields
from marshmallow.validate import Range


class BaseSchema(Schema):
    id = fields.Int(validate=Range(min=0), strict=True)
    created = fields.DateTime(format='iso')


class ProductSchema(BaseSchema):
    name = fields.String(required=True)
    description = fields.String(required=True)
    price = fields.Decimal(validate=Range(min=0, min_inclusive=False), places=2, required=True)


class CartItemSchema(BaseSchema):
    cart_id = fields.Int(validate=Range(min=0), strict=True)
    product_id = fields.Int(validate=Range(min=0), strict=True, required=True)
    quantity = fields.Int(validate=Range(min=1, max=5), strict=True, required=True)


class CartSchema(Schema):
    user_id = fields.Int(validate=Range(min=0), required=True)
    total_price = fields.Decimal(validate=Range(min=0), places=2, required=True)
    cart_items = fields.Nested(CartItemSchema(many=True), required=True)


# Responses schemas
class ProductsListResponseSchema(Schema):
    data = fields.Nested(ProductSchema(many=True), required=True)


class CartResponseSchema(Schema):
    data = fields.Nested(CartSchema(), required=True)


class NoContentResponseSchema(Schema):
    pass
