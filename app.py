from fastapi import FastAPI, HTTPException
from typing import Dict, Any, List,Optional
from pydantic import BaseModel
from datetime import datetime
import mysql.connector
import os
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import pymysql
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可 (開発時のみ推奨)
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation Error", "details": exc.errors()},
    )



@app.get("/")
async def root():
    return {"message": "Hello World"}

# MySQL接続情報
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "tech0-gen-8-step4-db-2.mysql.database.azure.com"),
    "user": os.getenv("MYSQL_USER", "Tech0Gen8TA2"),
    "password": os.getenv("MYSQL_PASSWORD", "gen8-1-ta@2"),
    "database": "class2_db"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# 商品マスタ取得API
TABLE_NAME = "m_product_hirojii"

@app.get("/product/{code}", response_model=Dict[str, Any])
def get_product(code: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM {TABLE_NAME} WHERE CODE = %s"
        cursor.execute(query, (code,))
        product = cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()
    return {"product": product if product else None}

# カート管理
cart = {}

class CartItem(BaseModel):
    code: str
    name: str
    price: int
    quantity: int = 1

@app.post("/cart/add")
def add_to_cart(item: CartItem):
    barcode = item.code
    if barcode in cart:
        cart[barcode]["quantity"] += item.quantity
    else:
        cart[barcode] = {
            "code": item.code,
            "name": item.name,
            "price": item.price,
            "quantity": item.quantity
        }
    return cart

# 購入API
class PurchaseRequest(BaseModel):
    emp_cd: str
    store_cd: str = Optional[str]  # 仕様書準拠で '30' をデフォルト
    pos_no: str = Optional[str]
    cart: List[CartItem] = [] # リスト型で受け取る

import pymysql
from datetime import datetime

@app.post("/purchase")
def purchase(request: PurchaseRequest):
    print("🚀 受信データ:", request.model_dump())  # JSONのデータを出力
    print("cart のデータ型:", type(request.cart))  # cart の型を確認
    print("cart の内容:", [item.model_dump() for item in request.cart])  # `cart` を辞書化して出力

    global cart
    if not request.cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total_price = sum(item.price * item.quantity for item in request.cart)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("✅ データベース接続成功")

        # 取引テーブル登録
        cursor.execute("""
            INSERT INTO transactions_hirojii (DATETIME, EMP_CD, STORE_CD, POS_NO, TOTAL_AMT)
            VALUES (%s, %s, %s, %s, %s)
        """, (datetime.now(), request.emp_cd or "9999999999", request.store_cd, request.pos_no, total_price))
        transaction_id = cursor.lastrowid
        print(f"✅ 取引テーブル登録成功 - 取引ID: {transaction_id}")

        # 取引明細登録
        transaction_details = []
        dtl_id = 1
        for item in request.cart:
            cursor.execute("SELECT PRD_ID FROM m_product_hirojii WHERE CODE = %s", (item.code,))
            product_data = cursor.fetchone()
            if not product_data:
                raise HTTPException(status_code=400, detail=f"Product {item.code} not found in master")

            prd_id = product_data[0]
            transaction_details.append((transaction_id, dtl_id, prd_id, item.code, item.name, item.price))
            dtl_id += 1

        print("🛠 取引明細データ:", transaction_details)  # データをデバッグ

        cursor.executemany("""
            INSERT INTO transaction_details_hirojii (TRD_ID, DTL_ID, PRD_ID, PRD_CODE, PRD_NAME, PRD_PRICE)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, transaction_details)

        print("✅ 取引明細テーブル登録成功")

        conn.commit()
        print("✅ コミット完了")

    except pymysql.MySQLError as e:
        conn.rollback()
        print("🚨 MySQLエラー発生:", str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    except Exception as e:
        conn.rollback()
        print("🚨 サーバーエラー発生:", str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    finally:
        cursor.close()
        conn.close()
        print("✅ データベース接続クローズ")

    cart.clear()

    return {"message": "Purchase successful", "total_price": total_price, "transaction_id": transaction_id}
