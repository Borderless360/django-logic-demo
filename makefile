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
	@echo ""
	@echo "  dlm-stats     : Show DLM execution-time statistics"
	@echo "  dlm-transitions: Show DLM active transitions"
	@echo "  dlm-anomalies : Show DLM detected anomalies"
	@echo "  fuckup-check  : Run fuckup_check (optional: make fuckup-check a='--since-days=7')"

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
worker-restart:
	docker compose -p $(PROJECT_NAME) restart demo-worker
test_locker:
	make manage s=demo c=test_locker
test_abstract:
	make manage s=demo c=test_abstract
test:
	make migrate
	make worker-restart
	docker compose -p $(PROJECT_NAME) exec demo pytest
test-one:
	make migrate
	make worker-restart
	docker compose -p $(PROJECT_NAME) exec demo pytest $(t) 

test-x:
	make test-one t=abstract/e2e/test_basic.py::test_transition_with_failed_callback

dlm-stats:
	make manage s=demo c=dlm_get_stats
dlm-transitions:
	make manage s=demo c=dlm_get_current_transitions
dlm-anomalies:
	make manage s=demo c=dlm_get_anomalies
dlm-clear-stats:
	make manage s=demo c=dlm_clear_stats
fuckup-check:
	docker compose -p $(PROJECT_NAME) exec demo python manage.py fuckup_check $(a)

celery-tasks:
	docker compose -p $(PROJECT_NAME) exec demo-worker celery -A demo.celery_app inspect registered
celery-active:
	docker compose -p $(PROJECT_NAME) exec demo-worker celery -A demo.celery_app inspect active
celery-recent:
	docker compose -p $(PROJECT_NAME) logs demo-worker --tail=500 --no-log-prefix | grep -E 'Task .+ (succeeded|failed|rejected|revoked)' | tail -20
celery-schedule:
	docker compose -p $(PROJECT_NAME) exec demo python -c "from demo.settings import CELERY_BEAT_SCHEDULE; import json; print(json.dumps(CELERY_BEAT_SCHEDULE, indent=2, default=str))"
