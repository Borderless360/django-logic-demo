PROJECT_NAME=django-logic-demo

info:
	echo "Usage: make <target> <args>"

build:
	export DOCKER_BUILDKIT=1 && \
	export COMPOSE_BAKE=true && \
	docker compose -p $(PROJECT_NAME) build
run:
	docker compose -p $(PROJECT_NAME) up
stop:
	docker compose -p $(PROJECT_NAME) stop 
down:
	docker compose -p $(PROJECT_NAME) down
reset:
	docker compose -p $(PROJECT_NAME) down -v

manage:
	docker compose -p $(PROJECT_NAME) exec $(s) python manage.py $(c)
make_migrations:
	make manage s=demo c=makemigrations
show-sql-migrate:
	docker compose -p $(PROJECT_NAME) exec demo python manage.py sqlmigrate $(a) $(m)
migrate:
	make manage s=demo c=migrate
