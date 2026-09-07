import os
import sqlite3
import json
import imagehash
from PIL.Image import Image
from image_normalizer import ImageNormalizer

class CacheService:
    def __init__(self, db_file="problem_cache.db", threshold=12):
        self.db_file = db_file
        self.threshold = threshold
        self.normalizer = ImageNormalizer()
        self._init_db()

    def _init_db(self):
        """SQLite 데이터베이스 및 테이블 초기화"""
        with sqlite3.connect(self.db_file) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS problem_cache (
                    hash_str TEXT,
                    model TEXT,
                    result_json TEXT
                )
            ''')
            # 검색 속도 향상을 위해 모델에 인덱스 생성
            conn.execute('CREATE INDEX IF NOT EXISTS idx_model ON problem_cache(model)')

    def get_cached_result(self, image: Image, current_model: str) -> dict:
        normalized_img = self.normalizer.normalize_for_hash(image)
        current_hash = imagehash.phash(normalized_img)
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            # 현재 모델로 저장된 캐시만 1차 필터링하여 가져옴
            cursor.execute("SELECT hash_str, result_json FROM problem_cache WHERE model = ?", (current_model,))
            rows = cursor.fetchall()
            
            for hash_str, result_json in rows:
                stored_hash = imagehash.hex_to_hash(hash_str)
                # 2차 판별: 해밍 거리 계산
                if current_hash - stored_hash <= self.threshold:
                    return json.loads(result_json)
                    
        return None

    def save_result(self, image: Image, result: dict, current_model: str):
        normalized_img = self.normalizer.normalize_for_hash(image)
        current_hash = imagehash.phash(normalized_img)
        result["model"] = current_model
        
        with sqlite3.connect(self.db_file) as conn:
            # 해시와 모델, JSON 문자열을 안전하게 DB에 Insert
            conn.execute(
                "INSERT INTO problem_cache (hash_str, model, result_json) VALUES (?, ?, ?)",
                (str(current_hash), current_model, json.dumps(result, ensure_ascii=False))
            )