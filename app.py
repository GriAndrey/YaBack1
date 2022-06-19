from flask import Flask, Response
import json
import sqlite3
from flask import request
import re
import math

app = Flask(__name__)
con = sqlite3.connect('shop.db')
cur = con.cursor()

con1 = sqlite3.connect('shop_copy.db')
cur1 = con1.cursor()

# Создание таблиц
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()

if not tables or ('shop' not in tables[0]):
    cur.execute(
        '''
        CREATE TABLE shop
        (id TEXT NOT NULL UNIQUE, type TEXT NOT NULL, name TEXT NOT NULL, date TEXT NOT NULL, parentId TEXT, price REAL, childrenCount INTEGER)
        ''')

cur1.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur1.fetchall()

if not tables or ('shop_copy' not in tables[0]):
    cur1.execute(
        '''
        CREATE TABLE shop_copy
        (id TEXT NOT NULL, type TEXT NOT NULL, name TEXT NOT NULL, date TEXT NOT NULL, parentId TEXT, price REAL, childrenCount INTEGER)
        ''')

con.commit()

con.close()

con1.commit()

con1.close()


@app.route('/')
def hello_world():
    return 'Hello World!'


# Функция импорта данных из json формата
@app.route('/imports', methods=['POST'])
def imports():
    # Подключение к таблицам
    con = sqlite3.connect('shop.db')
    cur = con.cursor()
    con1 = sqlite3.connect('shop_copy.db')
    cur1 = con1.cursor()

    data = request.json
    flag = True
    # Проверка валидности переданных данных
    try:
        for i in data['items']:
            # Проверка, что parentId не указывает на товар
            parent = i['parentId']
            parentId_finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()
            if parentId_finder:
                if parentId_finder[0][1] == 'OFFER':
                    return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')

            flag = flag * check_id(i['id']) * check_type(i['type']) * check_parentId(i['parentId']) * check_time(data['updateDate'])
            if i['type'] == 'OFFER':
                flag = flag * check_price(i['price'])

        if not flag:
            return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')

    except:
        return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')

    # Добавление переданных данных
    for i in data['items']:
        childrenCount = 0
        id = i['id']
        id_finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{id}%"').fetchall()
        # Условие того, что данный id передан впервые
        if not id_finder:
            try:
                price = None
                try:
                    if i['price'] is not None:
                        price = i['price']
                except:
                    pass
                dd = data["updateDate"]
                # при условии, что передает товар, необходимо пересчитать среднюю цену
                parent = i['parentId']
                if i['type'] == 'OFFER':


                    while 1:

                        if parent is None:
                            break

                        finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()
                        if finder[0][6] == 0:
                            cur.execute(f'UPDATE shop SET price = {price} WHERE id LIKE "%{parent}%"')
                        else:
                            price2 = (price + finder[0][6] * finder[0][5]) / (finder[0][6] + 1)
                            cur.execute(f'UPDATE shop SET price = {price2} WHERE id LIKE "%{parent}%"')

                        cur.execute(f'UPDATE shop SET childrenCount = childrenCount+1 WHERE id LIKE "%{parent}%"')
                        cur.execute(f'UPDATE shop SET date = "{dd}" WHERE id LIKE "%{parent}%"')

                        parent = finder[0][4]
                # Если передается категория, необходимо изменить дату изменения всех родителей категории
                else:
                    parent = i['parentId']

                    while 1:
                        finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()

                        if parent is None:
                            break

                        cur.execute(f'UPDATE shop SET date = "{dd}" WHERE id LIKE "%{parent}%"')

                        parent = finder[0][4]

                # Вставка элементов
                cur.execute('INSERT INTO shop VALUES (?,?,?,?,?,?,?)',
                            (i["id"], i["type"], i["name"], data["updateDate"], i["parentId"], price, childrenCount))

                # Добавляем все элементы во вторую таблицу и удаляем повторяющиеся, для /node/{id}/statistic
                output = cur.execute(f'SELECT * FROM shop').fetchall()
                for k in output:
                    cur1.execute(f'INSERT INTO shop_copy VALUES (?,?,?,?,?,?,?)',
                                 (k[0], k[1], k[2], k[3], k[4], k[5], k[6]))

                cur1.execute('DELETE FROM shop_copy WHERE EXISTS (SELECT 1 FROM shop_copy s2 '
                             'WHERE shop_copy.id = s2.id AND shop_copy.price = s2.price AND shop_copy.childrenCount = '
                             's2.childrenCount AND shop_copy.date = s2.date AND shop_copy.rowid > s2.rowid)')

                con.commit()
                con1.commit()
            except:
                con1.close()
                con.close()
                return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
        # Если данный id уже встречался
        else:
            # Если изменяется категория
            if id_finder[0][1] != i['type']:
                return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')


            try:
                price = None
                try:
                    if i['price'] is not None:
                        price = i['price']
                except:
                    pass

                dd = data["updateDate"]
                # при совпадении parentId
                if i['parentId'] == id_finder[0][4]:
                    if i['type'] == 'OFFER':
                        parent = i['parentId']

                        while 1:

                            if parent is None:
                                break

                            finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()

                            price2 = (price + finder[0][6] * finder[0][5] - id_finder[0][5]) / finder[0][6]
                            cur.execute(f'UPDATE shop SET price = {price2} WHERE id LIKE "%{parent}%"')

                            cur.execute(f'UPDATE shop SET date = "{dd}" WHERE id LIKE "%{parent}%"')

                            parent = finder[0][4]

                    else:
                        price = id_finder[0][5]
                        childrenCount = id_finder[0][6]
                        parent = i['parentId']

                        while 1:
                            finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()

                            if parent is None:
                                break

                            cur.execute(f'UPDATE shop SET date = "{dd}" WHERE id LIKE "%{parent}%"')

                            parent = finder[0][4]
                # При несовпадении parentId
                else:
                    if i['type'] == 'OFFER':
                        parent = i['parentId']
                        # Изменение новых родителей
                        while 1:

                            if parent is None:
                                break

                            finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()
                            if finder[0][6] == 0:
                                cur.execute(f'UPDATE shop SET price = {price} WHERE id LIKE "%{parent}%"')
                            else:
                                price2 = (price + finder[0][6] * finder[0][5]) / (finder[0][6] + 1)
                                cur.execute(f'UPDATE shop SET price = {price2} WHERE id LIKE "%{parent}%"')

                            cur.execute(
                                f'UPDATE shop SET childrenCount = childrenCount+1 WHERE id LIKE "%{parent}%"')
                            cur.execute(f'UPDATE shop SET date = "{dd}" where id LIKE "%{parent}%"')

                            parent = finder[0][4]

                        parent = id_finder[0][4]
                        # Изменение старых родителей
                        while 1:
                            if parent is None:
                                break

                            finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()
                            if finder[0][6] != 1:
                                price2 = (finder[0][6] * finder[0][5] - price) / (finder[0][6] - 1)
                            else:
                                price2 = None
                            if price2 == 0:
                                price2 = None
                            cur.execute(f'UPDATE shop SET price = {price2} WHERE id LIKE "%{parent}%"')

                            cur.execute(
                                f'UPDATE shop SET childrenCount = childrenCount-1 WHERE id LIKE "%{parent}%"')
                            cur.execute(f'UPDATE shop SET date = "{dd}" where id LIKE "%{parent}%"')

                            parent = finder[0][4]
                    # Если это категория
                    else:
                        parent = i['parentId']
                        price = id_finder[0][5]
                        print(price, id_finder[0][2])
                        childrenCount = id_finder[0][6]
                        # изменение новых родителей
                        while 1:

                            if parent is None:
                                break

                            finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()
                            if finder[0][6] == 0:
                                cur.execute(f'UPDATE shop SET price = {price} WHERE id LIKE "%{parent}%"')
                            else:
                                price2 = (price * childrenCount + finder[0][6] * finder[0][5]) / (finder[0][6] + childrenCount)
                                cur.execute(f'UPDATE shop SET price = {price2} WHERE id LIKE "%{parent}%"')

                            cur.execute(
                                f'UPDATE shop SET childrenCount = childrenCount+{childrenCount} WHERE id LIKE "%{parent}%"')
                            cur.execute(f'UPDATE shop SET date = "{dd}" WHERE id LIKE "%{parent}%"')

                            parent = finder[0][4]

                        parent = id_finder[0][4]
                        # Изменение старых родителей
                        while 1:
                            if parent is None:
                                break

                            finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()
                            if finder[0][6] != childrenCount:
                                price2 = (finder[0][6] * finder[0][5] - price*childrenCount) / (finder[0][6] - childrenCount)
                            else:
                                price2 = None
                            if price2 == 0:
                                price2 = None
                            cur.execute(f'UPDATE shop SET price = {price2} WHERE id LIKE "%{parent}%"')

                            cur.execute(
                                f'UPDATE shop SET childrenCount = childrenCount-{childrenCount} WHERE id LIKE "%{parent}%"')
                            cur.execute(f'UPDATE shop SET date = "{dd}" WHERE id LIKE "%{parent}%"')

                            parent = finder[0][4]
                # удаление старого значения и добавление нового (с сохранением price, если это была категория)
                id = i['id']
                cur.execute(f'DELETE FROM shop WHERE id LIKE "%{id}%"')
                cur.execute('INSERT INTO shop VALUES (?,?,?,?,?,?,?)',
                            (i["id"], i["type"], i["name"], data["updateDate"], i["parentId"], price, childrenCount))

                # Добавление новых элементов в таблицу shop_copy для получения статистики в будущем
                output = cur.execute(f'SELECT * FROM shop').fetchall()

                for k in output:
                    cur1.execute(f'INSERT INTO shop_copy VALUES (?,?,?,?,?,?,?)',
                                 (k[0], k[1], k[2], k[3], k[4], k[5], k[6]))


                cur1.execute('DELETE FROM shop_copy WHERE EXISTS (SELECT 1 FROM shop_copy s2 '
                             'WHERE shop_copy.id = s2.id AND shop_copy.name = s2.name AND shop_copy.price = s2.price  '
                             'AND shop_copy.parentId = s2.parentId AND shop_copy.childrenCount = s2.childrenCount AND '
                             'shop_copy.date = s2.date AND shop_copy.type = s2.type AND shop_copy.rowid > s2.rowid)')

                con.commit()
                con1.commit()
            except:
                con1.close()
                con.close()
                return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
    con1.close()
    con.close()
    return Response("{'message':'Ok'}", status=200, mimetype='application/json')


@app.route('/delete/<id>', methods=['DELETE'])
def delete(id):
    con = sqlite3.connect('shop.db')
    cur = con.cursor()

    con1 = sqlite3.connect('shop_copy.db')
    cur1 = con1.cursor()

    # Проверка валидности введенных данных
    flag = 1
    try:
        flag = flag * check_id(id)
        if not flag:
            return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
    except:
        return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')

    finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{id}%"').fetchall()
    if not finder:
        return Response("{'message':'Item not found'}", status=404, mimetype='application/json')
    parent = finder[0][4]
    price = finder[0][5]
    if price is None:
        price = 0
    children = finder[0][6]


    sumprice = price * children
    # Изменение цены и количества детей у родителей
    while 1:
        if parent is None:
            break

        finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{parent}%"').fetchall()

        newprice = (finder[0][5] * finder[0][6] - sumprice) / (finder[0][6] - children)
        cur.execute(f'UPDATE shop SET price = {newprice} WHERE id LIKE "%{parent}%"')

        cur.execute(f'UPDATE shop SET childrenCount = childrenCount-{children} WHERE id LIKE "%{parent}%"')
        parent = finder[0][4]

    ids = [id]
    ids1 = [id]
    # Удаление детей
    delete_rows(cur, ids, ids1)

    # Добавление всех изменений в таблицу shop_copy для получения статистики в будущем
    for i in ids1:
        cur1.execute(f'DELETE FROM shop_copy WHERE id LIKE "%{i}%"')

    output = cur.execute(f'SELECT * FROM shop').fetchall()
    for k in output:
        cur1.execute(f'INSERT INTO shop_copy VALUES (?,?,?,?,?,?,?)',
                     (k[0], k[1], k[2], k[3], k[4], k[5], k[6]))

    cur1.execute('DELETE FROM shop_copy WHERE EXISTS (SELECT 1 FROM shop_copy s2 '
                 'WHERE shop_copy.id = s2.id AND shop_copy.price = s2.price AND shop_copy.childrenCount = '
                 's2.childrenCount AND shop_copy.date = s2.date AND shop_copy.rowid > s2.rowid)')

    con1.commit()
    con1.close()
    con.commit()
    con.close()
    return Response("{'message':'Ok'}", status=200, mimetype='application/json')


# Функция удаления id и всех его детей
def delete_rows(cur, ids, ids1):
    if not ids:
        return
    finder = cur.execute(f'SELECT * FROM shop WHERE parentId LIKE "%{ids[0]}%"').fetchall()
    for i in finder:
        ids.append(i[0])
        ids1.append(i[0])
    cur.execute(f'DELETE FROM shop WHERE id LIKE "%{ids[0]}%"')
    ids.pop(0)
    delete_rows(cur, ids, ids1)


@app.route('/nodes/<id>', methods=['GET'])
def nodes(id):
    con = sqlite3.connect('shop.db')
    cur = con.cursor()

    flag = 1
    try:
        flag = flag * check_id(id)
        if not flag:
            return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
    except:
        return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')

    finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{id}%"').fetchall()
    if not finder:
        return Response("{'message':'Item not found'}", status=404, mimetype='application/json')

    result = {}
    print_nodes(id, result, cur)

    result = json.dumps(result)
    con.commit()
    con.close()
    return Response(response=result, status=200, mimetype='application/json')


# Функция вывода элемента и его детей
def print_nodes(id, dictionary, cur):
    finder = cur.execute(f'SELECT * FROM shop WHERE id LIKE "%{id}%"').fetchall()

    dictionary['type'] = finder[0][1]
    dictionary['name'] = finder[0][2]
    dictionary['id'] = finder[0][0]
    dictionary['parentId'] = finder[0][4]
    dictionary['price'] = math.floor(finder[0][5])
    dictionary['date'] = finder[0][3]
    # Просмотр количества детей
    if finder[0][6] == 0:
        dictionary['children'] = None
        return
    # Если дети есть, то добавляем столько же новых словарей, в которые рекурсивно заходим и пишем информацию о детях
    else:
        dictionary['children'] = []
        finder = cur.execute(f'SELECT * FROM shop WHERE parentId LIKE "%{id}%"').fetchall()

        k = len(finder)

        for j in range(k):
            dictionary['children'].append(dict())
        z = 0
        for i in finder:
            if z == k:
                return
            dictionary['children'][z] == print_nodes(i[0], dictionary['children'][z], cur)
            z += 1


@app.route('/sales', methods=['GET'])
def sales():
    con = sqlite3.connect('shop.db')
    cur = con.cursor()
    args = request.args['date']

    flag = 1
    try:
        flag = flag * check_time(args)
        if not flag:
            return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
    except:
        return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
    # Нахождение всех элементов, которые изменялись за последние 24ч
    finder = cur.execute(
        f'SELECT * FROM shop WHERE datetime(date) BETWEEN datetime("{args}", "-1 days") AND datetime("{args}")').fetchall()

    result = []
    # Вывод найденных элементов
    for i in finder:
        if i[1] == 'OFFER':
            result.append(
                {'type': i[1], 'name': i[2], 'id': i[0], 'price': math.floor(i[5]), 'parentId': i[4], 'date': i[3]})
    result = json.dumps(result)
    con.commit()
    con.close()

    return Response(response=result, status=200, mimetype='application/json')


@app.route('/node/<id>/statistic', methods=['GET'])
def statistics(id):
    con1 = sqlite3.connect('shop_copy.db')
    cur1 = con1.cursor()
    start = request.args['dateStart']
    end = request.args['dateEnd']

    finder = cur1.execute(f'SELECT * FROM shop_copy WHERE id LIKE "%{id}%"').fetchall()
    if not finder:
        return Response("{'message':'Item not found'}", status=404, mimetype='application/json')

    flag = 1
    try:
        flag = flag * check_time(start) * check_time(end) * check_id(id)
        if not flag:
            return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')
    except:
        return Response("{'message':'Validation Failed'}", status=400, mimetype='application/json')

    # Нахождение всех изменений в таблице shop_copy в промежутке между двумя заданными датами
    finder = cur1.execute(
        f'SELECT * FROM shop_copy WHERE id LIKE "%{id}%" AND datetime(date) BETWEEN datetime("{start}") AND datetime("{end}")')

    result = []
    for i in finder:
        if i[5] is None:
            result.append(
                {'type': i[1], 'name': i[2], 'id': i[0], 'price': None, 'parentId': i[4], 'date': i[3]})
        else:
            result.append(
                {'type': i[1], 'name': i[2], 'id': i[0], 'price': math.floor(i[5]), 'parentId': i[4], 'date': i[3]})
    result = json.dumps(result)

    con1.close()
    return Response(response=result, status=200, mimetype='application/json')


# Проверка корректности введенного id
def check_id(id):
    match = re.search(r'.{8}-.{4}-.{4}-.{4}-.{12}', id)
    if match is None:
        return False
    return True

# Проверка корректности введенного parentId
def check_parentId(id):
    if id is None:
        return True
    match = re.search(r'.{8}-.{4}-.{4}-.{4}-.{12}', id)
    if match is None and id is not None:
        return False

    return True

# Проверка корректности введенного date
def check_time(time):
    match = re.search(r'(\d){4}-(\d){2}-(\d){2}T(\d){2}:(\d){2}:(\d){2}\.(\d){3}Z', time)
    if match is None:
        return False
    return True

# Проверка корректности введенного price
def check_price(price):
    if not str(price).isdigit():
        return False
    return True

# Проверка корректности введенного type
def check_type(type):
    if type != 'OFFER' and type != 'CATEGORY':
        return False
    return True


if __name__ == "__main__":
    app.run()
