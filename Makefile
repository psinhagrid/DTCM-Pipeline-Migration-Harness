.PHONY: help build up up-ui down reset ps logs logs-backend logs-litellm logs-neo4j

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

build:  ## Build the backend image (fast-rlm-backend:local)
	docker compose build

up:  ## Build + start backend stack (neo4j + litellm + backend), detached
	docker compose up -d --build

up-ui:  ## Start full stack including the React frontend on :8080
	docker compose --profile ui up -d --build

down:  ## Stop stack, keep volumes
	docker compose down

reset:  ## Stop stack and DELETE volumes (neo4j data + Deno cache)
	docker compose down -v

ps:  ## Show running services
	docker compose ps

logs:  ## Follow logs for all services
	docker compose logs -f

logs-backend:  ## Follow backend (uvicorn) logs
	docker compose logs -f backend

logs-litellm:  ## Follow LiteLLM proxy logs
	docker compose logs -f litellm

logs-neo4j:  ## Follow Neo4j logs
	docker compose logs -f neo4j
