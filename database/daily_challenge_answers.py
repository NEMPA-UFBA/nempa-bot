import sqlite3
from datetime import datetime
import pytz

BAHIA_TZ = pytz.timezone('America/Bahia')


class DailyChallengeDbManager:
    def __init__(self, db_name="daily_challenges.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    user_id INTEGER,
                    question_id INTEGER,
                    answer TEXT,
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")

        # Migração: garantir coluna question_id em tabelas antigas
        try:
            self.cursor.execute("ALTER TABLE user_answers ADD COLUMN question_id INTEGER")
            self.conn.commit()
        except Exception:
            pass

    def _today_bahia(self) -> str:
        return datetime.now(BAHIA_TZ).strftime("%Y-%m-%d")

    def save_challenge_answer(self, message_id: int, user_id: int,
                               answer: str, question_id: int = None):
        try:
            today = self._today_bahia()
            self.cursor.execute('''
                INSERT INTO user_answers (message_id, user_id, question_id, answer, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (message_id, user_id, question_id, answer, today))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao salvar resposta: {e}")
            return False

    def check_user_answered_question(self, user_id: int, question_id: int) -> bool:
        """Verifica se o usuário já respondeu essa questão específica hoje."""
        try:
            today = self._today_bahia()
            self.cursor.execute('''
                SELECT COUNT(*) FROM user_answers
                WHERE user_id = ? AND question_id = ? AND DATE(date) = DATE(?)
            ''', (user_id, question_id, today))
            result = self.cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception as e:
            print(f"Erro ao verificar resposta: {e}")
            return False

    def check_user_answered(self, user_id: int) -> bool:
        """Verifica se o usuário respondeu qualquer questão hoje (compatibilidade)."""
        try:
            today = self._today_bahia()
            self.cursor.execute('''
                SELECT COUNT(*) FROM user_answers
                WHERE user_id = ? AND DATE(date) = DATE(?)
            ''', (user_id, today))
            result = self.cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception as e:
            print(f"Erro ao verificar resposta: {e}")
            return False

    def count_answers_for_question(self, question_id: int) -> int:
        try:
            self.cursor.execute(
                "SELECT COUNT(*) FROM user_answers WHERE question_id = ?",
                (question_id,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Erro ao contar respostas: {e}")
            return 0
    
    def delete_answers_by_id(self, answer_id: int):
        try:
            self.cursor.execute("DELETE FROM user_answers WHERE message_id = ?", (answer_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao deletar resposta: {e}")
            return False


db_daily_challenge_answer = DailyChallengeDbManager()