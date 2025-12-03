PROJECT_NAME=django-logic-demo

info:
	echo "Usage: make <target> <args>"

build:
	export DOCKER_BUILDKIT=1 && \
	export COMPOSE_BAKE=true && \
	docker compose -p $(PROJECT_NAME) build
run:
	docker compose -p $(PROJECT_NAME) up
