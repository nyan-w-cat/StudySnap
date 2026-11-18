import sqlite3
import json
import imagehash
from PIL.Image import Image

class CacheService:
    def __init__(self, db_file="problem_cache.db", threshold=2):
        """
        hash_size=16 (256비트 dHash) 기준 threshold=2는 99.2% 이상 화면이 일치할 때만 Cache Hit를 허용합니다.
        작업 표시줄 시계(1분 변경)나 커서 깜빡임 정도만 허용하고, 텍스트/수식이 조금이라도 다르면 무조건 새로 풉니다.
        """
        self.db_file = db_file
        self.threshold = threshold
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS problem_cache (
                    hash_str TEXT,
                    model TEXT,
                    result_json TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_model ON problem_cache(model)')

    def _compute_strict_hash(self, image: Image) -> imagehash.ImageHash:
        # ImageNormalizer 크롭을 제거하고, 원본 전체 화면을 16x16(256비트) 고해상도 dHash로 변환
        return imagehash.dhash(image, hash_size=16)

    def get_cached_result(self, image: Image, current_model: str) -> dict:
        current_hash = self._compute_strict_hash(image)
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT hash_str, result_json FROM problem_cache WHERE model = ?", (current_model,))
            rows = cursor.fetchall()
            
            for hash_str, result_json in rows:
                try:
                    stored_hash = imagehash.hex_to_hash(hash_str)
                    # 비트 길이가 같은(256비트) 해시끼리만 비교 (기존 64비트 데이터 충돌 방지)
                    if stored_hash.hash.shape == current_hash.hash.shape:
                        if current_hash - stored_hash <= self.threshold:
                            return json.loads(result_json)
                except Exception:
                    continue
                    
        return None

    def save_result(self, image: Image, result: dict, current_model: str):
        current_hash = self._compute_strict_hash(image)
        result["model"] = current_model
        
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO problem_cache (hash_str, model, result_json) VALUES (?, ?, ?)",
                (str(current_hash), current_model, json.dumps(result, ensure_ascii=False))
            )
