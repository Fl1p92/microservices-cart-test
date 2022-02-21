#!/bin/bash

GREEN='\033[1;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Run customers and cart pytest...\nRunning customers tests by pytest...${NC}"
docker exec -it -e DEBUG='False' customers pytest customers/
scripts/run_pytest_cart.sh
