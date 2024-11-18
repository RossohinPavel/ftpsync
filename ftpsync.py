"""
Синхронизация данных по FTP протоколу. Логика работы похожа на git.

Инструкция для работы со скриптом.
1) Создаем конигурационный файл. Сделать это можно командой 
ftpsync.py --config
Сразу добавляйте этот файл в .gitignore, так как он будет содержать личную информацию
2) Заполняем в конфигурационном файле host, user, password, ftp_path (директория на сервере) и массив exclude.
Exclude - должен содержать имена папок и файлов, которые не должны загружаться на сервер.
3) Конфигурационный файл нужно поместить в корень каталога, который будем синхронизировать.
4) Вызываем скрипт командой ftpsync.py -p <относительный или абсолютный путь> до папки.

Не создавайте файлы с именем __catalog_action__ )))
"""
import argparse
from pathlib import Path
import json
import os
from ftplib import FTP


parser = argparse.ArgumentParser(description='ftp_synchronizer')
parser.add_argument(
    'path', 
    nargs='?',
    type=str, 
    default='.', 
    help='Каталог, сожержание которого нужно загрузить'
)
parser.add_argument(
    '--config', 
    type=bool, 
    default=False, 
    action=argparse.BooleanOptionalAction, 
    help='Создает конигурационный файл.'
)
namespace = parser.parse_args()


CACHE_FILENAME = 'ftps.json'
ROOT_PATH = Path(os.path.abspath(namespace.path))
def create_config():
    """Создает конфиг для загрузки"""
    sample = {
        "host": "", "user": "", "password": "", "ftp_path": "/",
        "exclude": ["ftpsync.py", "ftps.json", "venv", "__pycache__", ".git"],
        "files": {}
    }
    with open(ROOT_PATH / CACHE_FILENAME, 'w', encoding='utf-8') as file:
        json.dump(sample, file, indent=4)
    print(f'Конфигурационный файл создан: {ROOT_PATH / CACHE_FILENAME}.\nЗаполните его и добавьте в gitignore.')


if namespace.config:
    create_config()
    exit()


try:
    with open(ROOT_PATH / 'ftps.json', 'r') as file:
        CACHE = json.load(file)
except FileNotFoundError:
    print('Невозможно открыть файл конфигурации. Проверьте целостность или наличие ftps.json')


FILES = CACHE['files']
EXCLUDE = set(CACHE['exclude'])


# Расшифровка списка действий
# -1 - Файл нужно удалить с сервера.
#  0 - С файлом ничего не нужно делать
#  1 - Файл нужно загрузить на сервер 


def file_handler(relative_path: str, name: str):
    """Проверка последнего изменения файлов"""
    if relative_path not in FILES:
        FILES[relative_path] = {}
    catalog = FILES[relative_path]
    if name not in catalog:
        catalog[name] = {'last_modify': 0, 'action': 0}
    file = catalog[name]
    current_modify_time = os.path.getmtime(f'{ROOT_PATH}{relative_path}/{name}')
    last_modify_time = file['last_modify']
    if current_modify_time > last_modify_time:
        file['last_modify'] = current_modify_time
        file['action'] = 1
    else:
        file['action'] = 0


ROOT_PATH_STR = str(ROOT_PATH)
def walk_on(file_path: str):
    """Рекурсивный обход по файлам"""
    abs_path = ROOT_PATH_STR + '/' + file_path
    for name in os.listdir(abs_path):
        if name in EXCLUDE:
            continue
        if os.path.isdir(Path(abs_path, name)):
            walk_on(f'{file_path}/{name}')
        if os.path.isfile(Path(abs_path, name)):
            file_handler(file_path, name)


walk_on('')



def action_on_catalog(ftp: FTP, catalog: str) -> str:
    """Действия с каталогом. Возвращает имя конечного каталога"""
    *relative_paths, dir = catalog.split('/')
    server_path = FTP_PATH + '/'.join(relative_paths)
    ftp.cwd(server_path)
    if dir:
        try:
            ftp.mkd(dir)
        except:
            pass
        ftp.cwd(dir)
    return dir


COUNT = 0
def action_on_file(ftp: FTP, catalog: str, name: str, meta: dict) -> int:
    """Действия с файлами. возвращает логическое значение. True - если файл был удален и False, если нет."""    
    if meta['action'] == -1:    # Помеченный на удаление
        try:
            ftp.delete(name)
            print(f'deleted: {catalog} {name}')
            return True
        except:
            pass
    global COUNT
    if meta['action'] == 1:
        with open(f'{ROOT_PATH}{catalog}/{name}', 'rb') as upload_file:
            ftp.storbinary('STOR ' + name, upload_file)
            print(f'uploaded: {catalog} {name}')
            COUNT += 1
    meta['action'] = -1
    return False


def remove_catalog(ftp: FTP, dir: str, files: dict):
    """Логика удаления каталога"""
    if dir and len(files) == 0:
        try:
            ftp.cwd('..')
            ftp.rmd(dir)
            return True
        except Exception as e:
            return False


HOST = CACHE.get('host')
USER = CACHE.get('user')
PASSWORD = CACHE.get('password')
FTP_PATH = CACHE.get('ftp_path')
with FTP(HOST) as ftp:
    ftp.login(USER, PASSWORD)
    for catalog, files in tuple(FILES.items()):
        dir = action_on_catalog(ftp, catalog)
        for name, meta in tuple(files.items()):
            result = action_on_file(ftp, catalog, name, meta)
            if result:
                FILES[catalog].pop(name)
        result = remove_catalog(ftp, dir, files)
        if result:
            FILES.pop(catalog)
        ftp.cwd("/")


with open(ROOT_PATH / CACHE_FILENAME, 'w', encoding='utf-8') as file:
        json.dump(CACHE, file, indent=4)
print(f'Синхронизация закончена. {COUNT} файлов было обновлено.')
