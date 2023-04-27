[![Linters](https://github.com/CyberPhysics-Platform/batchmq/actions/workflows/linting.yml/badge.svg)](https://github.com/CyberPhysics-Platform/batchmq/actions/workflows/linting.yml)
### BatchMQ service
- python >= 3.11
- mypy & pyright & pylint & flake8
- prometheus /metrics

#### TODO:
- тесты
- запуск повторной обработки сообщений из очередей с ошибками
    - учесть возможные "перемешивания" сообщений, которые должны вставляться по очереди

#### Архитектурная диаграмма
<img src="./static/arch.jpg" width="400px">

#### Диаграмма последовательностей
<img src="./static/seq.jpg">
