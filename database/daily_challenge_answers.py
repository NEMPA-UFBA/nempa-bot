import sqlite3

class DailyChallengeDbManager:
    def __init__(self, db_name="daily_challenges.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_answers (
                    message_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    answer TEXT,
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")

    def save_challenge_answer(self, message_id, user_id, answer):
        try:
            self.cursor.execute('''
                INSERT INTO user_answers (message_id, user_id, answer)
                VALUES (?, ?, ?)
            ''', (message_id, user_id, answer))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao salvar resposta do desafio: {e}")
            return False
    
    def check_user_answered(self, user_id, date):
        try:
            self.cursor.execute('''
                SELECT COUNT(*) FROM user_answers
                WHERE user_id = ? AND DATE(date) = DATE(?)
            ''', (user_id, date))
            result = self.cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception as e:
            print(f"Erro ao verificar resposta do usuário: {e}")
            return False

db_daily_challenge_answer = DailyChallengeDbManager()  # Instância global do gerenciador de banco de dados