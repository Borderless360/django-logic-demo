PROJECT_NAME=django-logic-demo


info:
	@echo "Usage: make <target> <args>"
	@echo "Targets:"
	@echo ""
	@echo "  build : Build the Docker image"
	@echo "  run   : Run the Docker container"
	@echo "  stop  : Stop the Docker container"
	@echo "  down  : Remove the Docker container"
	@echo "  reset : Remove the Docker container and volume"
	@echo ""
	@echo "  manage          : Run a Django management command"
	@echo "  make_migrations : Make migrations"
	@echo "  show-sql-migrate: Show SQL migrations"
	@echo "  migrate         : Apply migrations"
	@echo ""
	@echo "  test_locker   : Run locker tests"
	@echo "  test_abstract : Run abstract tests"
	@echo "  test          : Run all tests"

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
	rm django-logic.log

manage:
	docker compose -p $(PROJECT_NAME) exec $(s) python manage.py $(c)
make_migrations:
	make manage s=demo c=makemigrations
show-sql-migrate:
	docker compose -p $(PROJECT_NAME) exec demo python manage.py sqlmigrate $(a) $(m)
migrate:
	make manage s=demo c=migrate
test_locker:
	make manage s=demo c=test_locker
test_abstract:
	make manage s=demo c=test_abstract
test:
	make migrate
	docker compose -p $(PROJECT_NAME) exec demo pytest
test-one:
	docker compose -p $(PROJECT_NAME) exec demo pytest abstract/e2e/test_basic.py::test_happy_path
