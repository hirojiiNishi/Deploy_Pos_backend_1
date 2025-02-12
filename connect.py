
import os
import tempfile
import mysql.connector
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote
import psutil
from dotenv import load_dotenv

# .env を読み込む
load_dotenv()


# SSL証明書の取得
ssl_cert = os.getenv("SSL_CA_CERT")

if not ssl_cert:
    raise ValueError("❌ SSL_CA_CERT が設定されていません！")

# デバッグ: SSL 証明書の長さを出力 (証明書が空ではないかチェック)
print(f"✅ SSL_CA_CERT がロードされました (長さ: {len(ssl_cert)} バイト)")

# 証明書の改行処理
ssl_cert = ssl_cert.strip()  # 余分なスペースや改行を削除

# 環境変数の取得
db_user = os.getenv("MYSQL_USER")
db_password = os.getenv("MYSQL_PASSWORD")
db_host = os.getenv("MYSQL_HOST")
db_name = os.getenv("MYSQL_DATABASE")

# 必須環境変数のチェック
missing_vars = [var for var, value in {
    "MYSQL_USER": db_user,
    "MYSQL_PASSWORD": db_password,
    "MYSQL_HOST": db_host,
    "MYSQL_DATABASE": db_name,
    "SSL_CA_CERT": ssl_cert
}.items() if not value]

if missing_vars:
    raise ValueError(f"❌ 必須環境変数が設定されていません: {', '.join(missing_vars)}")

# パスワードを URL エンコード（ `@` → `%40` ）
db_password_encoded = quote(db_password)



# SSL証明書の一時ファイル作成
def create_ssl_cert_tempfile():
    pem_content = ssl_cert.replace("\\n", "\n").replace("\\", "")
    temp_pem = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="w")
    temp_pem.write(pem_content)
    temp_pem.close()
    return temp_pem.name

ssl_ca_path = create_ssl_cert_tempfile()


# SQLAlchemy エンジンの作成
DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password_encoded}@{db_host}/{db_name}?ssl_ca={ssl_ca_path}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# セッションの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# MySQL に直接接続する関数
def get_db_connection():
    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        ssl_ca=ssl_ca_path
    )


# 環境変数のチェック（デバッグ用）
print(f"✅ MySQL USER: {db_user}")
print(f"✅ MySQL HOST: {db_host}")
print(f"✅ MySQL DATABASE: {db_name}")