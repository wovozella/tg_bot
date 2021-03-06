from db_interface import select
from calendar import monthrange
from datetime import datetime, date
from json import dumps

month_in_seconds = 2_592_000  # 30 days

# for avoiding not clearly raised exceptions in valid_input()
built_in_exceptions = {chr(i) for i in range(97, 123)}

days = {0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
        4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'}

del_translate = {'Отдаёшь': 'give', 'Берёшь': 'take'}
input_translate = {'/give': 'отдать', '/take': 'взять'}



# It's too complicated to easily iterate dictionaries with undefined nesting
# that has more than one key, so the chat id stores in global variable,
# which returns in another function.
# You must call only get_chat_id function
__chat_id = 0
def __extract_chat_id(dictionary):
    global __chat_id
    for key in dictionary:
        value = dictionary[key]
        if isinstance(value, dict):
            if key == 'chat':
                __chat_id = value['id']
                return
            __extract_chat_id(value)
def get_chat_id(dictionary):
    __extract_chat_id(dictionary)
    return __chat_id


def valid_input(update):
    now = datetime.now()
    try:
        _date, time = update['message']['text'].split(' ')
        start, end = time.split('-')
        month, day = _date.split('.')

        day = int(day)
        month = int(month)
        year = now.year  # Despite user don't input year, it's necessary for database

        if not 1 <= month <= 12:
            raise Exception('Месяц должен быть между 1 и 12')
        if not 1 <= day <= monthrange(now.year, month)[1]:
            raise Exception('День должен быть между 1 и максимальным днём '
                            'в указанном месяце')
        if now.month == 12 and month == 1:  # december - january case
            year += 1

        entered_time = datetime(year, month, day).timestamp()
        current_time = datetime(now.year, now.month, now.day).timestamp()
        if entered_time - current_time > month_in_seconds:
            raise Exception('Нельзя указать часы больше чем на 30 дней вперёд')
        if entered_time - current_time < 0:
            raise Exception('Дата должна быть не меньше текущего дня')

        start = int(start)
        end = int(end)
        if day == now.day:
            if start <= now.hour:
                raise Exception('Первый час должен быть больше нынешнего часа')

        if start >= end:
            raise Exception('Последний час должен быть после первого')
        if not 8 <= start <= 23:
            raise Exception('Первый час должен быть между 8 и 23')
        if not 9 <= end <= 24:
            raise Exception('Последний час должен быть между 9 и 24')

        return date(year, month, day), start, end
    # Probably better to clearly describe all Exceptions, that may be raised
    except Exception as error:
        if set(error.args[0]).intersection(built_in_exceptions):
            return 'Некорректный или неполный ввод'
        return error.args[0]



# 'time' arg for this function is return of valid_input function
# personal arg for defining either find intersections with others couriers
# or with yourself
def time_intersect(time, table, user_id, personal=False):
    _date, start, end = time

    condition = f'WHERE user_id != {user_id}'
    if personal:
        condition = f'WHERE user_id = {user_id}'

    if str(_date) not in [i[0] for i in select(table, 'DISTINCT date', condition)]:
        return False
    condition += f' and date = "{_date}"'

    intersected = []
    for time_interval in select(table, 'start_hour, end_hour, user_id', condition):
        if set(range(*time_interval[:-1])).intersection(set(range(start, end))):
            intersected.append(time_interval)

    return intersected


def get_message(table_name, user_id, specific=False):
    """
    Format message for showing records from tables
    "specific" argument needs for showing courier his own times to edit/delete them

    Returning message looks like that:
    05.14 (date MM.DD bold text)
    courier_name first_hour-last_hour (With link to user)
    another_courier 15-23

    05.16
    and_another_courier 8-24
    """
    condition = f'user_id != {user_id}'
    if specific:
        condition = f'user_id = {user_id}'

    message = ''
    # creating dict with date as a key
    dates = {Date[0]: [] for Date in select(table_name, 'DISTINCT date',
                                            f'WHERE {condition} ORDER BY date')}
    # filling dates dict
    for Date, *details in select(
            table_name,
            conditions=f"WHERE {condition} ORDER BY date, start_hour"):
        dates[Date].append(details)

    for Date, values in dates.items():
        times = ''
        for time in values:
            *hours, name, user_id = time
            courier_name = f'<a href="tg://user?id={user_id}">{name}</a> '
            if specific:
                courier_name = ''
            times += f'{courier_name}{hours[0]}-{hours[1]}\n'

        # Formatting date from YYYY-MM-DD to (DD.MM weekday)
        weekday = date(*[int(i) for i in Date.split('-')]).weekday()
        Date = Date.split('-')
        Date = Date[1] + '.' + Date[2]

        new_line = '\n'
        if specific:
            new_line = ''
        message += f'<b>{Date} {days[weekday]}</b>\n' \
                   f'{times}{new_line}'
    return message


def inline_buttons(list_of_buttons: list):
    buttons = []
    for row in list_of_buttons:
        buttons.append([{'text': button, 'callback_data': button} for button in row])
    return dumps({'inline_keyboard': buttons})


# get last word of table name as a parameter (give or take)
# and simply change to one another
def reverse_table(table_name):
    if table_name == 'time_to_give':
        return 'time_to_take'
    return 'time_to_give'
