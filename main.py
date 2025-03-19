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
def sort_articles():
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
        print(f"\n✅ Ordenamiento completado en {elapsed_time:.6f} segundos.\n")

        for article in sorted_articles:
            date = str(article["publication_date"]) if article["publication_date"] else "Desconocida"
            if not date:
                date = "Desconocida"  # Evita que aparezca "<12"
            print(f"{article['id']:<5} {article['nombreBD']:<10} {date:<12} {article['authors'][:27]:<30} {article['title'][:37]:<40} {article['link']}")

    cursor.close()
    conn.close()


# -----------------  🚀 Ejecutar el Script ------------------

if __name__ == "__main__":
    #reset_table()

    fetch_articles_scopus()
    #fetch_articles_ieee()
    #sort_articles()