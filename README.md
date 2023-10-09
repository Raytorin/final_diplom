### Перед запуском необходимо в файле .env указать почту и пароль.

### Для запуска docker-compose использовать следующую команду (Beta)
 ```sudo docker-compose up --build -d```

### Запуск без docker
```python manage.py collectstatic```
```python manage.py makemigrations```
```python manage.py migrate```
```python manage.py runserver```
 
### В проекте присутствуют защищенные методы, для доступа к ним необходимо в http-запросе в заголовке указать Authorization со значением Token
### Пример token
### Authorization: Token <полученный токен>

### /users/
### GET запрос позволяет получить данные пользователя
### POST запрос - регистрирует нового пользователя (сообщение приходит на почту)
### Пример входных данных
```
{
    "first_name": "first_name", 
    "last_name": "last_name", 
    "username": "Test", 
    "email": "example@gmail.com", 
    "password": "dhfh23!", 
    "password2": "dhfh23!"
}
```
### PATCH - изменяет данные пользователя
### Пример
```
{
    "current_password": "dhfh23!", 
    "password": "dadaQqe2", 
    "password2": "dadaQqe2"
}
```

### /users/auth/
### POST запрос производит авторизацию по почте и паролю
### Примечание, с неподтвержденной почтой токен не выдается
### Пример
```
{
    "email": "example@gmail.com", 
    "password": "dadaQqe2"
}
```

### /users/password_reset/
### POST - отправляет на почту данные для сброса пароля
### Пример
```
{
    "email": "example@gmail.com"
}
```

### /user/password_reset/confirm/
### POST позволяет сбросить пароль
### Пример
```
{
    "email": "example@gmail.com", 
    "token": "<токен из сообщения>", 
    "password": "Hokw123!", 
    "password2": "Hokw123!"
}
```

### /user/contact/
### GET - получить список контактов
### POST позволяет создаь контакт
### Пример
```
{
    "city": "Санкт-Петербург",
    "street": "улица Ленина",
    "house": "1",
    "structure": "1",
    "building": "1",
    "apartment": "1",
    "phone": "+79990000000"
}
```

### /user/contact/1/
### GET - получить контакт 1
### PATCH - изменить контакт 1
### DELETE - удалить контак 1

### /shops/
### GET - вывести список магазинов
### POST - создать новый магазин
### Пример 
```
{
    "name": "Re-store",
    "url": "https://re-store.ru/",
    "email": "restore@gmail.com"
}
```

### /shops/1/
### GET - получение магазина 1
### PATCH - изменение данных магазина 1

### /categories/
### GET - получить список всех категорий

### /categories/1/
### GET - получить категорию 1

### /products/
### GET - Получить товаров доступных для покупки
### Для данного запроса доступна фильтрация
* name - фильтрация по названию товара
* shop - фильтрация по названию магазина
* min_price - минимальная цена
* max_price - максимальная цена=
* min_price_rrc - минимальная рекомендованная цена в рознице
* max_prie_rrc - максимальная рекомендованная цена в рознице
* category - фильтрация по категории
* quantity - фильтрация по количестку товара

### Пример
``` /products/?name=Iphone15ProMax&min_price=180000&max_price=300000 ```
### Данный запрос выдаст нам Iphone15ProMax в ценовом диапозоне 180000 - 300000

### /product/1/
### GET - получить товар 1

### /basket/
### GET - выводит информацию о корзине
### POST - позволяет добавить товары
### DELETE - удаляет товары из корзины с указанным id
### Пример
```
[
    {
        "product_info": 1,
        "quantity": 1
    },
    {
        "product_info": 2,
        "quantity": 3
    }
]
```

### /order/
### GET - выводит все заказы (поддерживает фильтрацию по телефону и по дате создания)
### POST - размещает заказ на заданный контакт(адрес)
### Пример, показывает заказ по номеру и дате заказа
```
    /order/?created_at_before=2023-10-10&phone=9990001122
```

### /order/1/
### GET - позволяет получить заказ 1

###  /order/seller_order/1/
### DELETE - удаляет заказ для магазина с индентификатором 1 


### /partner/product/upload/
### POST - импорт товаров из формата .yaml

### /partner/products/
### GET - выводит список всех товаров магазина (доступна фильтрация)
* name - название товара
* min_price - минимальная цена
* max_price - максимальная цена
* min_price_rrc - минимальная рекомендованная цена в рознице
* max_price_rrc - максимальная рекомендованная цена в рознице
* category - категория товара
* quantity -  количество товара
* product_external_id - фильтрация по id товару
* category_external_id - фильтрация по id категории
### Пример, вывод Iphone15ProMax, где есть 5 телефонов в наличии
```
    /partner/products/?name=Iphone15ProMax&quantity=5
```

### POST запрос создает новый товар
### Пример
```
{
    "external_id": 70000,
    "product": {
        "name": "MateBook"
    },
    "category": {
            "name": "Laptop",
            "external_id": 15
    },
    "product_parameters": [
        {
            "parameter": "efficiency",
            "value": "hight"
        },
        {
            "parameter": "Color",
            "value": "Grey"
        }
    ],
    "quantity": 10,
    "price": 78000,
    "price_rrc": 90000
}
```

### /partner/products/1/
### GET - выдвет товар магзина с индентификатором 1
### PATCH - изменяет товар магазина с индентификатором 1
### DELETE - удалить товар из наличия
### Пример
```
{
    "product_parameters": [
        {
            "parameter": "efficiency",
            "value": "low"
        },
        {
            "parameter": "color",
            "value": "black"
        },
        {
            "parameter": "cyrillic",
            "value": "yes"
        }
    ],
    "price": 90000,
    "price_rrc": 98000,
    "quantity": 3
}
```

### /partner/state/
### GET - получить текущий статус магазиан
### POST позволяет изменить статус магазина
### Пример
```
{
    "state": "open"
}
```

### /partner/orders/
### GET - выдает список всех заказов (присутствует филтрация по почте, телефону и дате создания)
### Пример, выдвет заказы удовлетворяющие дате создания, телефону и почте
```
    /partner/orders/?created_at_before=2023-10-10&phone=9990001122&email=example@gmail.com
```

### /partner/orders/1/
### GET - выводит заказ магазина с индентификатором 1
### PATCH - изменяет заказ с индентификатором 1
### Возможные статусы заказов
* new
* confirmed
* assembled
* sent
* delivered
* canceled
### Для защиты, статусы canceled и delivered нельзя изменить
### также нельзя изменить стоимость когда заказ sent, delivered и canceled 
### Пример
```
{
    "state": "canceled"
}
```
