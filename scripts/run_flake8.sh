#!/bin/bash

GREEN='\033[1;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Run customers and cart flake8...${NC}"
docker exec -it customers flake8 --config customers/.flake8 customers
docker exec -it cart flake8 --config cart/.flake8 cart
