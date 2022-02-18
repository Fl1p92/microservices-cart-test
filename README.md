# microservices-cart-test

docker exec -it cart alembic -c cart/alembic.ini revision --message="Data migration. Add carts" --autogenerate
docker exec -it cart alembic -c cart/alembic.ini upgrade head

cp .env.example .env && cp cart/.env.example cart/.env && cp customers/.env.example customers/.env
docker cp customers:/home/micro_user/protobufs/ .
