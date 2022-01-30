# microservices-cart-test

docker exec -it customers alembic revision --message="Migration message" --autogenerate
docker exec -it customers alembic upgrade head