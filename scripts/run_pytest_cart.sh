#!/bin/bash

RED='\033[0;31m'
GREEN='\033[1;32m'
NC='\033[0m' # No Color

CUSTOMERS_CONTAINER_IS_RUNNING="$( docker container inspect -f '{{.State.Status}}' customers )"
CUSTOMERS_SERVICE_AVAILABLE="$(curl -s -w "%{http_code}" -o /dev/null http://127.0.0.1:8081/api/v1/auth/login/)"

if [[ $CUSTOMERS_CONTAINER_IS_RUNNING == "running" && $CUSTOMERS_SERVICE_AVAILABLE == "405" ]]; then
  echo -e "${GREEN}Running cart integration tests by pytest...${NC}"
  docker exec -it -e DEBUG='False' cart pytest cart/
else
  echo -e "${RED}Error! customers container is not running or the server is down! You can't run cart integration tests by pytest.${NC}"
fi
