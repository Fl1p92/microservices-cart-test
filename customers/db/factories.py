import factory

from customers.db.models import User


USER_TEST_PASSWORD = 'testPass123'


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):

    class Meta:
        model = User
        strategy = factory.BUILD_STRATEGY

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')

    @factory.lazy_attribute
    def password(self):
        return User.make_user_password_hash(USER_TEST_PASSWORD)

    @factory.lazy_attribute
    def email(self):
        return f'{self.first_name}.{self.last_name}@example.com'.lower()
