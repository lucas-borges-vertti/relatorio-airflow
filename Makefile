.PHONY: help build up down logs dev-logs airflow-logs db-logs clean restart

help:
	@echo "Available commands:"
	@echo "  make build              - Build Docker images"
	@echo "  make up                 - Start containers"
	@echo "  make down               - Stop containers"
	@echo "  make restart            - Restart all containers"
	@echo "  make clean              - Remove containers and volumes"
	@echo "  make logs               - View all logs"
	@echo "  make dev-logs           - View NestJS logs"
	@echo "  make airflow-logs       - View Airflow logs"
	@echo "  make db-logs            - View PostgreSQL logs"
	@echo "  make shell              - Access NestJS container shell"
	@echo "  make airflow-shell      - Access Airflow container shell"
	@echo "  make init-airflow       - Initialize Airflow database and user"

build:
	docker compose build

up:
	docker compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	docker compose ps

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

dev-logs:
	docker compose logs -f nestjs-api

airflow-logs:
	docker compose logs -f airflow-webserver

db-logs:
	docker compose logs -f postgres

clean:
	docker compose down -v
	rm -rf airflow/logs/*
	@echo "Cleaned up containers and volumes"

shell:
	docker compose exec nestjs-api /bin/sh

airflow-shell:
	docker compose exec airflow-webserver /bin/bash

init-airflow:
	docker compose exec -T airflow-webserver airflow db init
	docker compose exec -T airflow-webserver airflow users create \
		--username airflow \
		--firstname Airflow \
		--lastname Admin \
		--role Admin \
		--email admin@vertti.com \
		--password airflow
	@echo "Airflow initialized"

ps:
	docker compose ps

health:
	@echo "Checking NestJS..."
	@curl -s http://localhost:3000/api/reports | jq . || echo "NestJS not responding"
	@echo ""
	@echo "Checking Airflow..."
	@curl -s -u airflow:airflow http://localhost:8081/api/v1/dags | jq . || echo "Airflow not responding"
