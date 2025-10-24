.PHONY: help build run web stop clean logs init-db

help:
	@echo "Available commands:"
	@echo "  make build    - Build Docker images"
	@echo "  make init-db  - Initialize database"
	@echo "  make run      - Run full pipeline (init-db + analysis)"
	@echo "  make web      - Start web dashboard"
	@echo "  make all      - Run everything (init-db + analysis + web)"
	@echo "  make stop     - Stop all containers"
	@echo "  make clean    - Remove containers and generated files"
	@echo "  make logs     - View logs"

build:
	docker-compose build

init-db:
	docker-compose up init-db

run:
	docker-compose up init-db analysis

web:
	docker-compose up -d web

all:
	docker-compose build
	docker-compose up init-db analysis
	docker-compose up -d web

stop:
	docker-compose down

clean:
	docker-compose down -v
	rm -f database/*.db database/*.db-*
	rm -f plots/*.png

logs:
	docker-compose logs -f

