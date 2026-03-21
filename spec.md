# Django Logic Demo
Sandbox to make experiments and e2e tests for Django Logic.

## Constraints
- Python 3.12+, Django 4.2+, Celery
- Everything must be covered by tests using pytest.

## Structure
- abstract      - e2e tests with abstract data 
- clickhouse    - client ClickHouse and related things 
- core          -  
- demo          - main django app
- django_logic          - copy of original django logic lib
- django_logic_celery   - copy of original django logic celery lib
- django_logic_ext      - copy of app from gv repo
- django_logic_monitoring - django app for monitoring django logic logs
- invoice       - e2e test based on invoice domain
- locker        - e2e test based on locker domain
- utils - utils for all 
- v2 - alternative implementation of django logic
- v3 - alternative implementation «One Transaction — One Class» of django logic
- v4 - evolutionary refactoring of django logic (typed context, strict permissions, fixed error handling)

## Infrastructure

The project runs entirely inside Docker Compose. 
All day-to-day operations go through `makefile` targets — 
never run Django/Celery/pytest on the host directly.
