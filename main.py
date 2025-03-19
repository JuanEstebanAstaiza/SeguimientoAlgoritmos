import requests
import mysql.connector
import time
import xml.etree.ElementTree as ET

# 🔹 Configuración de APIs
API_KEY_SCOPUS = "70c102fffa4eee4b0b2d1700b3a279ff"
API_KEY_IEEE = "tu_api_key_ieee"
BASE_URL_SCOPUS = "https://api.elsevier.com/content/search/scopus"
BASE_URL_IEEE = "http://ieeexploreapi.ieee.org/api/v1/search/articles"

# 🔹 Configuración de la base de datos MySQL
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "articleservice"
}

# -----------------  🔗 Conexión a la Base de Datos ------------------

def connect_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error:
        return None

def create_database_and_connect():
    conn = connect_db()
    if conn:
        return conn  # Si la BD ya existe, usamos la conexión

    try:
        temp_conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        cursor = temp_conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        print(f"✅ Base de datos '{DB_CONFIG['database']}' creada/verificada.")
        cursor.close()
        temp_conn.close()
        return connect_db()
    except mysql.connector.Error as err:
        print(f"❌ Error al crear la base de datos: {err}")
        return None

def create_table():
    conn = create_database_and_connect()
    if conn is None:
        return

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombreBD VARCHAR(20) NOT NULL,
            authors VARCHAR(255),
            publication_date DATE,
            title VARCHAR(255) NOT NULL UNIQUE,
            link VARCHAR(255)
        )
    """)
    conn.commit()
    print("✅ Tabla 'articles' creada/verificada.")
    cursor.close()
    conn.close()

def reset_table():
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor()
    try:
        cursor.execute("TRUNCATE TABLE articles")  # Elimina todos los registros y resetea el ID AUTO_INCREMENT
        conn.commit()
        print("✅ Tabla 'articles' reseteada exitosamente.")
    except mysql.connector.Error as err:
        print(f"⚠️ Error al resetear la tabla: {err}")
    finally:
        cursor.close()
        conn.close()

def create_table2():
    conn = create_database_and_connect()
    if conn is None:
        return

    cursor = conn.cursor()

    # 🔥 Elimina la tabla si ya existe
    cursor.execute("DROP TABLE IF EXISTS articles")

    # 🔄 Crea la tabla desde cero con 'nombreBD'
    cursor.execute("""
        CREATE TABLE articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombreBD VARCHAR(20) NOT NULL,
            authors VARCHAR(255),
            publication_date DATE,
            title VARCHAR(255) NOT NULL UNIQUE,
            link VARCHAR(255)
        )
    """)
    conn.commit()
    print("✅ Tabla 'articles' creada/verificada.")
    cursor.close()
    conn.close()
# -----------------  🔍 Verificar y Guardar Artículos ------------------

def article_exists(title):
    conn = connect_db()
    if conn is None:
        return False
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles WHERE title = %s", (title,))
    exists = cursor.fetchone()[0] > 0
    cursor.close()
    conn.close()
    return exists

def save_article(nombreBD, authors, publication_date, title, link):
    if article_exists(title):
        print(f"⚠️ El artículo '{title}' ya está en la base de datos. Saltando...")
        return

    conn = connect_db()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO articles (nombreBD, authors, publication_date, title, link)
            VALUES (%s, %s, %s, %s, %s)
        """, (nombreBD, authors, publication_date, title, link))
        conn.commit()
        print(f"✅ [{nombreBD}] Artículo '{title}' guardado en la base de datos.")
    except mysql.connector.Error as err:
        print(f"⚠️ Error al guardar '{title}': {err}")
    finally:
        cursor.close()
        conn.close()

# -----------------  🔍 Obtener Artículos de Scopus ------------------

def fetch_articles_scopus(query="Human Computer Interaction", max_results=10000):
    articles_saved = 0
    start_index = 0

    while articles_saved < max_results:
        params = {
            "query": query,
            "apiKey": API_KEY_SCOPUS,
            "count": 25,
            "start": start_index
        }
        headers = {
            "X-ELS-APIKey": API_KEY_SCOPUS,
            "Accept": "application/json"
        }

        response = requests.get(BASE_URL_SCOPUS, params=params, headers=headers)

        if response.status_code != 200:
            print("❌ Error en la solicitud:", response.json())
            break

        data = response.json()
        articles = data.get("search-results", {}).get("entry", [])

        if not articles:
            print("⚠️ No se encontraron más artículos en Scopus.")
            break

        for article in articles:
            title = article.get("dc:title", "Sin título")
            link = article.get("link", [{}])[0].get("@href", "Sin enlace")
            publication_date = article.get("prism:coverDate", "0000-00-00")
            authors = article.get("dc:creator", "Desconocido")

            if isinstance(authors, list):
                authors_list = ", ".join(authors)
            else:
                authors_list = authors

            save_article("Scopus", authors_list, publication_date, title, link)
            articles_saved += 1

            if articles_saved >= max_results:
                break

        start_index += 25
        time.sleep(0.1)

    print(f"✅ Se guardaron {articles_saved} artículos de Scopus.")

# -----------------  🔍 Obtener Artículos de IEEE Xplore ------------------

def fetch_articles_ieee(query="Human Computer Interaction", max_results=10):
    params = {
        "apikey": API_KEY_IEEE,
        "format": "xml",
        "max_records": max_results,
        "querytext": query
    }

    response = requests.get(BASE_URL_IEEE, params=params)

    if response.status_code != 200:
        print("❌ Error en la solicitud a IEEE:", response.text)
        return

    root = ET.fromstring(response.content)
    articles_saved = 0

    for article in root.findall(".//document"):
        title = article.findtext("title", "Sin título")
        link = article.findtext("htmlLink", "Sin enlace")
        publication_date = article.findtext("publicationYear", "0000") + "-01-01"
        authors_list = [author.text for author in article.findall("authors/author")]
        authors = ", ".join(authors_list) if authors_list else "Desconocido"

        save_article("IEEE", authors, publication_date, title, link)
        articles_saved += 1

        if articles_saved >= max_results:
            break

    print(f"✅ Se guardaron {articles_saved} artículos de IEEE Xplore.")

# -----------------  📜 Listar Artículos ------------------



def list_articles():
    conn = connect_db()
    if conn is None:
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles ORDER BY publication_date DESC")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        print("\n📜 Lista de artículos almacenados:")
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)


        for article in articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            if not date:
                date = "Desconocida"  # Evita que aparezca "<12"
            print(f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

    cursor.close()
    conn.close()


import time
def timsort_articles():
    conn = connect_db()
    if conn is None:
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, nombreBD, authors, publication_date, title, link FROM articles ORDER BY publication_date DESC")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        sorted_articles = sorted(articles, key=lambda x: x['title'])  # TimSort
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            if not date:
                date = "Desconocida"  # Evita que aparezca "<12"
            print(f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


def comb_sort(arr, key):
    gap = len(arr)
    shrink = 1.3  # Factor de reducción recomendado
    sorted_ = False

    while not sorted_:
        gap = int(gap / shrink)
        if gap <= 1:
            gap = 1
            sorted_ = True

        for i in range(len(arr) - gap):
            if arr[i][key] > arr[i + gap][key]:
                arr[i], arr[i + gap] = arr[i + gap], arr[i]
                sorted_ = False


def sort_articles_combsort():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo Comb Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        comb_sort(articles, key='title')  # Comb Sort
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

    cursor.close()
    conn.close()

def selection_sort(arr, key):
    """
    Implementación del algoritmo Selection Sort para ordenar una lista de diccionarios
    según la clave especificada.
    """
    n = len(arr)
    for i in range(n):
        min_index = i
        for j in range(i + 1, n):
            if arr[j][key] < arr[min_index][key]:
                min_index = j
        arr[i], arr[min_index] = arr[min_index], arr[i]  # Intercambio de elementos

def sort_articles_selection_sort():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo Selection Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        selection_sort(articles, key='title')  # Selection Sort
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

    cursor.close()
    conn.close()


class TreeNode:
    def _init_(self, key, data):
        self.key = key
        self.data = data
        self.left = None
        self.right = None


class BST:
    def _init_(self):
        self.root = None

    def insert(self, key, data):
        if self.root is None:
            self.root = TreeNode(key, data)
        else:
            self._insert_recursive(self.root, key, data)

    def _insert_recursive(self, node, key, data):
        if key < node.key:
            if node.left is None:
                node.left = TreeNode(key, data)
            else:
                self._insert_recursive(node.left, key, data)
        else:
            if node.right is None:
                node.right = TreeNode(key, data)
            else:
                self._insert_recursive(node.right, key, data)

    def inorder_traversal(self, node, result):
        if node:
            self.inorder_traversal(node.left, result)
            result.append(node.data)
            self.inorder_traversal(node.right, result)

    def get_sorted_elements(self):
        result = []
        self.inorder_traversal(self.root, result)
        return result


def tree_sort(articles):
    bst = BST()
    for article in articles:
        bst.insert(article['title'], article)
    return bst.get_sorted_elements()


def sort_articles_tree_sort():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo Tree Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()
        sorted_articles = tree_sort(articles)  # Tree Sort
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

    cursor.close()
    conn.close()


import time


def pigeonhole_sort(articles, key):
    """
    Implementación de Pigeonhole Sort para ordenar los artículos por el campo 'title'.
    """
    if not articles:
        return []

    # Encontrar el mínimo y máximo de las claves de ordenamiento
    min_key = min(articles, key=lambda x: x[key])[key]
    max_key = max(articles, key=lambda x: x[key])[key]

    # Crear los agujeros (pigeonholes)
    size = ord(max_key[0]) - ord(min_key[0]) + 1  # Basado en el primer carácter
    pigeonholes = [[] for _ in range(size)]

    # Colocar los artículos en los agujeros correspondientes
    for article in articles:
        index = ord(article[key][0]) - ord(min_key[0])
        pigeonholes[index].append(article)

    # Leer los artículos en orden desde los agujeros
    sorted_articles = []
    for hole in pigeonholes:
        for item in sorted(hole, key=lambda x: x[key]):  # Ordenar dentro del agujero
            sorted_articles.append(item)

    return sorted_articles


def sort_articles_pigeonhole():
    """
    Ordena los artículos almacenados en la base de datos utilizando Pigeonhole Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        sorted_articles = pigeonhole_sort(articles, key='title')  # Pigeonhole Sort
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

    cursor.close()
    conn.close()


import time
from collections import defaultdict


def bucket_sort(articles):
    """
    Implementación de Bucket Sort para ordenar artículos por el campo 'title'.
    """
    if not articles:
        return []

    # Determinar el número de cubetas
    num_buckets = min(len(articles), 26)  # Se usa 26 asumiendo un alfabeto en inglés
    buckets = defaultdict(list)

    # Distribuir elementos en los buckets según la primera letra del título
    for article in articles:
        first_char = article['title'][0].lower()
        index = ord(first_char) - ord('a') if 'a' <= first_char <= 'z' else 25  # No letras van al último bucket
        buckets[index].append(article)

    # Ordenar individualmente cada bucket (usamos sorted, pero puede ser otra estrategia más óptima)
    sorted_articles = []
    for i in range(num_buckets):
        sorted_articles.extend(sorted(buckets[i], key=lambda x: x['title']))

    return sorted_articles


def sort_articles_bucket_sort():
    """
    Ordena los artículos almacenados en la base de datos utilizando BucketSort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        sorted_articles = bucket_sort(articles)
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


def quicksort(arr, key):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x[key] < pivot[key]]
    middle = [x for x in arr if x[key] == pivot[key]]
    right = [x for x in arr if x[key] > pivot[key]]
    return quicksort(left, key) + middle + quicksort(right, key)


def sort_articles_quicksort():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo QuickSort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        sorted_articles = quicksort(articles, 'title')  # QuickSort
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


import heapq


def heapsort_articles(articles):
    """
    Implementa HeapSort para ordenar los artículos por el campo 'title'.
    """
    heap = [(article['title'], article) for article in articles]
    heapq.heapify(heap)  # Construir el heap (O(n))
    return [heapq.heappop(heap)[1] for _ in range(len(heap))]  # Extraer elementos ordenados (O(n log n))


def sort_articles_heapsort():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo HeapSort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()  # ⏱ Inicia el cronómetro
        sorted_articles = heapsort_articles(articles)  # HeapSort
        end_time = time.time()  # ⏱ Finaliza el cronómetro

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


def bitonic_sort(arr, up=True):
    """
    Implementación de Bitonic Sort.
    """
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    first_half = bitonic_sort(arr[:mid], True)
    second_half = bitonic_sort(arr[mid:], False)

    return bitonic_merge(first_half + second_half, up)


def bitonic_merge(arr, up):
    """
    Fase de fusión de Bitonic Sort.
    """
    if len(arr) <= 1:
        return arr

    bitonic_compare(arr, up)

    mid = len(arr) // 2
    first_half = bitonic_merge(arr[:mid], up)
    second_half = bitonic_merge(arr[mid:], up)

    return first_half + second_half


def bitonic_compare(arr, up):
    """
    Realiza comparaciones y swaps en la secuencia bitónica.
    """
    dist = len(arr) // 2
    for i in range(dist):
        if (arr[i]['title'] > arr[i + dist]['title']) == up:
            arr[i], arr[i + dist] = arr[i + dist], arr[i]


def sort_articles_bitonic():
    """
    Ordena los artículos almacenados en la base de datos utilizando Bitonic Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()
        sorted_articles = bitonic_sort(articles, up=True)
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


def gnome_sort(arr, key):
    """Implementación del algoritmo Gnome Sort."""
    index = 0
    while index < len(arr):
        if index == 0 or arr[index][key] >= arr[index - 1][key]:
            index += 1
        else:
            arr[index], arr[index - 1] = arr[index - 1], arr[index]
            index -= 1
    return arr


def sort_articles_gnome():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo Gnome Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()
        sorted_articles = gnome_sort(articles, 'title')
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


def binary_search(arr, target, start, end):
    """Realiza una búsqueda binaria para encontrar la posición de inserción."""
    while start < end:
        mid = (start + end) // 2
        if arr[mid]['title'] < target['title']:
            start = mid + 1
        else:
            end = mid
    return start


def binary_insertion_sort(arr):
    """Ordena una lista de diccionarios por la clave 'title' usando Binary Insertion Sort."""
    for i in range(1, len(arr)):
        key_item = arr[i]
        insert_pos = binary_search(arr, key_item, 0, i)
        arr = arr[:insert_pos] + [key_item] + arr[insert_pos:i] + arr[i + 1:]
    return arr


def sort_articles_binary_insertion():
    """
    Ordena los artículos almacenados en la base de datos utilizando Binary Insertion Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()
        sorted_articles = binary_insertion_sort(articles)
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()


from collections import defaultdict


def radix_sort(arr, key):
    """
    Implementa el algoritmo Radix Sort para ordenar una lista de diccionarios por una clave específica.
    """
    if not arr:
        return []

    max_length = max(len(str(item[key])) for item in arr)  # Longitud máxima de la clave 'title'

    for digit_pos in range(max_length - 1, -1, -1):
        buckets = defaultdict(list)  # Usa un diccionario para evitar errores de rango

        for item in arr:
            title = str(item[key]).lower()  # Convertimos a minúsculas para orden consistente
            char = ord(title[digit_pos]) if digit_pos < len(title) else 0
            buckets[char].append(item)

        arr = [item for k in sorted(buckets.keys()) for item in buckets[k]]  # Ordena por clave ASCII

    return arr


def sort_articles_radix():
    """
    Ordena los artículos almacenados en la base de datos utilizando el algoritmo Radix Sort
    y calcula el tiempo de ejecución del proceso.
    """
    conn = connect_db()
    if conn is None:
        print("❌ No se pudo conectar a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombreBD, authors, publication_date, title, link FROM articles")
    articles = cursor.fetchall()

    if not articles:
        print("⚠️ No hay artículos almacenados en la base de datos.")
    else:
        start_time = time.time()
        sorted_articles = radix_sort(articles, key='title')  # Radix Sort
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        # Imprimir los artículos ordenados
        print("=" * 120)
        print(f"{'ID':<5} {'Fuente':<10} {'Fecha':<12} {'Autores':<30} {'Título':<40} {'Enlace'}")
        print("=" * 120)

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            print(
                f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos. n = {len(articles)}")

    cursor.close()
    conn.close()
# -----------------  🚀 Ejecutar el Script ------------------

if __name__ == "_main_":

   create_database_and_connect()
   create_table()
   create_table2()


