#!/bin/bash

GREEN='\033[1;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Build customers and cart images...${NC}"
DOCKER_BUILDKIT=1 docker build . -f customers/Dockerfile -t customers:0.1.0 --secret id=ca.key,src=ca.key
DOCKER_BUILDKIT=1 docker build . -f cart/Dockerfile -t cart:0.1.0 --secret id=ca.key,src=ca.key
