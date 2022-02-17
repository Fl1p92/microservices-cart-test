# microservices-cart-test

docker exec -it customers alembic revision --message="Migration message" --autogenerate
docker exec -it customers alembic upgrade head

cp .env.example .env && cp cart/.env.example cart/.env && cp customers/.env.example customers/.env
docker cp customers:/home/micro_user/protobufs/ .
