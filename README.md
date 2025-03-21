# Telegram-бот для публикации объявлений с модерацией

## Описание проекта

Telegram-бот, позволяющий пользователям создавать и публиковать объявления с возможностью модерации. Бот поддерживает два типа объявлений:
1. **Обычные объявления** — создаются бесплатно.
2. **VIP-объявления** — требуют оплаты бонусными баллами.

Бот также включает систему модерации, административную панель и управление балансом пользователей.

## Функциональные возможности

### 1. Пользовательские функции
- **Создание объявлений**:
  - Добавление фотографий.
  - Ввод описания.
  - Отправка на модерацию.
- **VIP-объявления**:
  - Создание платных объявлений.
  - Использование бонусных баллов.
- **Удаление объявлений**:
  - Удаление опубликованных объявлений.
- **Пополнение баланса**:
  - Пополнение бонусного баланса через администратора.

### 2. Админ-функции
- **Модерация объявлений**:
  - Одобрение/отклонение объявлений.
  - Блокировка пользователей.
- **Управление балансом**:
  - Просмотр баланса пользователей.
  - Изменение баланса.
- **Настройка VIP-цен**:
  - Установка стоимости VIP-объявлений.
- **Статистика**:
  - Просмотр статистики объявлений за месяц и полгода.

### 3. Интерфейс
- Главное меню с кнопками:
  - Добавить объявление.
  - Создать VIP-объявление.
  - Удалить объявление.
  - Админ-панель.

## Установка и запуск

### Необходимые компоненты
- Python 3.7+
- Библиотеки: \`aiogram\`, \`aiosqlite\`

### Шаги установки

1. **Клонирование репозитория**
   \`\`\`bash
   git clone https://github.com/yourusername/telegram-ads-bot.git
   cd telegram-ads-bot
   \`\`\`

2. **Установка зависимостей**
   \`\`\`bash
   pip install aiogram aiosqlite
   \`\`\`

3. **Настройка конфигурации**
   Замените значения в файле \`bot.py\`:
   - \`TOKEN\`: Токен вашего Telegram-бота.
   - \`ADMIN_IDS\`: Список ID администраторов.
   - \`MODERATION_GROUP_ID\`: ID группы для модерации объявлений.
   - \`CHANNEL_ID\`: ID канала для публикации объявлений.
   - \`PAYMENT_TOKEN\`: Токен платежной системы (если используется).

4. **Инициализация базы данных**
   База данных создается автоматически при первом запуске. Все данные хранятся в файле \`bot.db\`.

5. **Запуск бота**
   \`\`\`bash
   python bot.py
   \`\`\`

## Использование

### Пользовательский режим
1. Запустите бота командой \`/start\`.
2. Используйте кнопки для:
   - Создания обычных или VIP-объявлений.
   - Удаления опубликованных объявлений.
   - Просмотра баланса и пополнения баланса.

### Админ-режим
1. Используйте кнопку "Админка" для доступа к административным функциям.
2. Управляйте объявлениями, пользователями и настройками через админ-панель.

## Структура кода

### База данных
- **Таблица \`users\`**:
  - \`user_id\`: Уникальный идентификатор пользователя.
  - \`balance\`: Бонусный баланс.
  - \`is_banned\`: Статус блокировки.
- **Таблица \`ads\`**:
  - \`id\`: Уникальный идентификатор объявления.
  - \`user_id\`: ID пользователя.
  - \`images\`: JSON-массив с фотографиями.
  - \`description\`: Описание объявления.
  - \`status\`: Статус объявления (\`draft\`, \`moderation\`, \`published\`, \`rejected\`).
  - \`is_vip\`: Флаг VIP-объявления.
- **Таблица \`vip_prices\`**:
  - \`price\`: Стоимость VIP-объявления.

### Обработчики
- **/start**:
  - Приветствие и отображение главного меню.
- **Добавление объявлений**:
  - Обработка фотографий и описания.
  - Отправка на модерацию.
- **VIP-объявления**:
  - Проверка баланса.
  - Создание и отправка VIP-объявлений.
- **Модерация**:
  - Одобрение/отклонение объявлений.
  - Блокировка пользователей.
- **Админ-панель**:
  - Управление пользователями.
  - Настройка VIP-цен.
  - Просмотр статистики.

### Клавиатуры
- **Главное меню**:
  - Кнопки для быстрого доступа к функциям.
- **Inline-клавиатуры**:
  - Управление объявлениями и модерация.

### FSM (Finite State Machine)
- Управление состояниями пользователя:
  - Добавление фотографий.
  - Ввод описания.
  - Подтверждение публикации.

## Лицензия

[MIT](https://choosealicense.com/licenses/mit/)

## Поддержка

Если у вас возникли вопросы или проблемы, пожалуйста, свяжитесь с [вашим контактом].

## Благодарности

- Реализовано с использованием библиотек [\`aiogram\`](https://github.com/aiogram/aiogram) и [\`aiosqlite\`](https://github.com/omnilib/aiosqlite).
EOF
