# microservices-cart-test

docker exec -it customers alembic revision --message="Migration message" --autogenerate
docker exec -it customers alembic upgrade head

cp .env.example .env && cp cart/.env.example cart/.env && cp customers/.env.example customers/.env
docker cp customers:/home/micro_user/protobufs/ .
DOCKER_BUILDKIT=1 docker build . -f customers/Dockerfile -t customers:0.1.0 --secret id=ca.key,src=ca.key
DOCKER_BUILDKIT=1 docker build . -f cart/Dockerfile -t cart:0.1.0 --secret id=ca.key,src=ca.key
