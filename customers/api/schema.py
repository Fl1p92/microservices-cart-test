from marshmallow import Schema, fields, validates_schema, ValidationError
from marshmallow.validate import Length, Range


class BaseSchema(Schema):
    id = fields.Int(validate=Range(min=0), strict=True)
    created = fields.DateTime(format='iso')


class UserSchema(BaseSchema):
    email = fields.Email(required=True)
    first_name = fields.String(validate=Length(min=1, max=256))
    last_name = fields.String(validate=Length(min=1, max=256))
    password = fields.String(required=True, validate=Length(min=7), load_only=True)
    is_admin = fields.Boolean()


class JWTTokenSchema(Schema):
    token = fields.String(required=True)
    user = fields.Nested(UserSchema(exclude=('password', )))


class UserPatchSchema(Schema):
    email = fields.Email()
    first_name = fields.String(validate=Length(min=1, max=256))
    last_name = fields.String(validate=Length(min=1, max=256))
    is_admin = fields.Boolean()


class UserChangePasswordSchema(Schema):
    new_password = fields.String(required=True, validate=Length(min=7), load_only=True)
    confirm_new_password = fields.String(required=True, validate=Length(min=7), load_only=True)

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        if data['new_password'] != data['confirm_new_password']:
            raise ValidationError({'confirm_new_password': ["The two password fields didn't match."]})


# Responses schemas
class UserDetailsResponseSchema(Schema):
    data = fields.Nested(UserSchema(exclude=('password', )), required=True)


class JWTTokenResponseSchema(Schema):
    data = fields.Nested(JWTTokenSchema(), required=True)


class UserListResponseSchema(Schema):
    data = fields.Nested(UserSchema(exclude=('password', ), many=True), required=True)


class NoContentResponseSchema(Schema):
    pass
