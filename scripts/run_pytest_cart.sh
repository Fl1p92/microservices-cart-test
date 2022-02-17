#!/bin/bash

RED='\033[0;31m'
GREEN='\033[1;32m'
NC='\033[0m' # No Color

if [ "$( docker container inspect -f '{{.State.Status}}' customers )" == "running" ]; then
  echo -e "${GREEN}Running cart integration tests by pytest...${NC}"
  docker exec -it -e DEBUG='False' cart pytest cart/
else
  echo -e "${RED}Error! customers container is not running! You can't run cart integration tests by pytest.${NC}"
fi
